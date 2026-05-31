"""Ingestion pipeline: parse a CBSE past-paper PDF and auto-tag questions via an LLM.

`Ingestor` is the coordinator. It runs the pipeline and persists Question rows
(verified=False). Four seams are injected as adapters:

* `Parser`           — turns PDF bytes into plain text. Default: `PdfplumberParser`.
* `Tagger`           — assigns chapter_slug + cognitive_level. Default: `LLMTagger`.
* `DiagramExtractor` — crops images from the PDF and associates them with questions.
                       Default: `PdfplumberDiagramExtractor`.
* `AnswerSource`     — parses an answer/marking-scheme PDF into
                       `{question_number: answer_text}`. Default:
                       `MarkingSchemeAnswerSource`. Consumed by
                       `Ingestor.apply_answers`.

Match strategy for `apply_answers` is a documented coordinator invariant: the
n-th answer in the parsed scheme is assigned to the n-th unverified Question row
ordered by id. CBSE marking schemes mirror the question paper's numbering so
the picker doesn't need a more clever key today. Revisit when out-of-order
schemes appear.

Pure text predicates (`strip_hindi`, `segment_questions`, `_detect_numerical`,
`_mentions_diagram`) are not configurable and remain module-level. Tests inject
stub adapters into Ingestor — no module-level patching.
"""

from __future__ import annotations

import difflib
import hashlib
import io
import json
import re
from dataclasses import dataclass
from typing import Protocol

import pdfplumber

from .llm import LLMClient, make_llm_client
from .models import Chapter, CognitiveLevel, Question

_DEVANAGARI_RE = re.compile(r"[ऀ-ॿ]+")
_SECTION_RE = re.compile(r"\bSECTION\s+([A-E])\b", re.IGNORECASE)
_QNUM_RE = re.compile(r"^\s*(?:Q\.?\s*)?(\d{1,2})\s*[.)]\s+", re.MULTILINE)
_MARKS_RE = re.compile(r"\[(\d)\]|\((\d)\s*[Mm]arks?\)")
_OPTION_RE = re.compile(r"\(([A-D])\)\s*(.*?)(?=\s*\([A-D]\)|$)", re.DOTALL)
# Numerical: equation-like text, SI units, or standalone numbers with units.
_NUMERICAL_RE = re.compile(
    r"""
    \d+\.?\d*\s*(?:m/s|kg|mol|J|W|N|Pa|°C|K|A|V|Ω|Hz|m|cm|nm|km|g|mg|L|mL)\b
    | =\s*[-+]?\d
    | \b\d{1,3}\s*[×x]\s*10\^?\d
    """,
    re.VERBOSE | re.IGNORECASE,
)
_DIAGRAM_RE = re.compile(r"\bfig(?:ure)?\.?\s*\d*\b|\bdiagram\b", re.IGNORECASE)
# Shape-detection regexes for structured content parsing.
_AR_ASSERTION_RE = re.compile(
    r"Assertion\s*\(A\)\s*[:\-]\s*(.*?)(?=\s*Reason\s*\(R\))",
    re.IGNORECASE | re.DOTALL,
)
_AR_REASON_RE = re.compile(
    r"Reason\s*\(R\)\s*[:\-]\s*(.*?)(?=\s*\(A\)\s|\Z)",
    re.IGNORECASE | re.DOTALL,
)
_OR_LINE_RE = re.compile(r"^\s*OR\s*$", re.MULTILINE)
_CASE_SUBPART_RE = re.compile(
    r"^\s*\(([a-d]|i{1,3}|iv|v|vi)\)\s+",
    re.MULTILINE | re.IGNORECASE,
)
_LA_SUBPART_RE = re.compile(
    r"^\s*[\(\[]([ivx]+|[a-f])[\)\]]\s+",
    re.MULTILINE | re.IGNORECASE,
)
_SCHEME_ANS_LINE_RE = re.compile(
    r"""
    ^\s*
    (?:Q\.?\s*)?          # optional "Q" prefix
    (\d{1,2})             # question number
    [.)\s]+               # separator
    (.+)                  # answer text (rest of line)
    """,
    re.VERBOSE,
)
_SCHEME_ANS_HEADER_RE = re.compile(r"\bAns(?:wer)?\.?\s*[:—-]?\s*(.+)", re.IGNORECASE)

SECTION_DEFAULT_MARKS: dict[str, int] = {"A": 1, "B": 2, "C": 3, "D": 5, "E": 4}
SECTION_DEFAULT_QTYPE: dict[str, str] = {
    "A": "mcq",
    "B": "very_short_answer",
    "C": "short_answer",
    "D": "long_answer",
    "E": "case_based",
}

_TAG_BATCH = 30


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def strip_hindi(text: str) -> str:
    """Remove Devanagari characters; collapse residual whitespace."""
    cleaned = _DEVANAGARI_RE.sub(" ", text)
    cleaned = re.sub(r" {2,}", " ", cleaned)
    return cleaned.strip()


def _parse_options(text: str) -> tuple[list[dict], str]:
    """Extract MCQ option dicts from text; return (options, question_stem)."""
    opt_start = text.find("(A)")
    if opt_start == -1:
        return [], text
    stem = text[:opt_start].strip()
    options_text = text[opt_start:]
    options = [
        {"label": m.group(1), "text": m.group(2).strip()}
        for m in _OPTION_RE.finditer(options_text)
        if m.group(2).strip()
    ]
    return options, stem


def _fingerprint(text: str) -> str:
    """MD5 of normalised text — used for de-duplication."""
    normalised = re.sub(r"\s+", " ", text.lower().strip())
    normalised = re.sub(r"[^\w\s]", "", normalised)
    return hashlib.md5(normalised.encode()).hexdigest()


def _detect_numerical(text: str) -> bool:
    """True if the question involves numerical calculation (SI units, equations)."""
    return bool(_NUMERICAL_RE.search(text))


def _mentions_diagram(text: str) -> bool:
    """True if the question text references a figure/diagram (image may be absent)."""
    return bool(_DIAGRAM_RE.search(text))


def _parse_assertion_reason(text: str) -> dict | None:
    """Detect Assertion (A)/Reason (R) pattern; return structured content or None."""
    a_match = _AR_ASSERTION_RE.search(text)
    r_match = _AR_REASON_RE.search(text)
    if not a_match or not r_match:
        return None
    assertion_text = a_match.group(1).strip()
    reason_text = r_match.group(1).strip()
    if not assertion_text or not reason_text:
        return None
    # Parse MCQ options from text after the reason block to avoid matching
    # the "Assertion (A):" prefix as an option label.
    options_text = text[r_match.end() :]
    options, _ = _parse_options(options_text)
    return {
        "assertion": [{"type": "paragraph", "text": assertion_text}],
        "reason": [{"type": "paragraph", "text": reason_text}],
        "options": [
            {"label": o["label"], "content": [{"type": "paragraph", "text": o["text"]}]}
            for o in options
        ],
    }


def _parse_case_based(text: str) -> dict | None:
    """Detect passage + lettered/roman subparts; return structured content or None."""
    matches = list(_CASE_SUBPART_RE.finditer(text))
    if len(matches) < 2:
        return None
    passage_text = text[: matches[0].start()].strip()
    if not passage_text or len(passage_text) < 20:
        return None
    subparts = []
    for idx, m in enumerate(matches):
        label = m.group(1).lower()
        start = m.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        content_text = text[start:end].strip()
        if content_text:
            subparts.append(
                {
                    "label": label,
                    "marks": 1,
                    "content": [{"type": "paragraph", "text": content_text}],
                }
            )
    if len(subparts) < 2:
        return None
    return {
        "passage": [{"type": "paragraph", "text": passage_text}],
        "subparts": subparts,
    }


def _parse_internal_choice(text: str) -> dict | None:
    """Detect standalone OR line between two question blocks; return choices or None."""
    parts = _OR_LINE_RE.split(text, maxsplit=1)
    if len(parts) < 2:
        return None
    choice_a, choice_b = parts[0].strip(), parts[1].strip()
    if not choice_a or not choice_b:
        return None
    return {
        "choices": [
            {
                "displayStyle": "or",
                "chooseCount": 1,
                "options": [
                    {
                        "label": "A",
                        "content": [{"type": "paragraph", "text": choice_a}],
                    },
                    {
                        "label": "B",
                        "content": [{"type": "paragraph", "text": choice_b}],
                    },
                ],
            }
        ]
    }


def _parse_long_answer_subparts(text: str) -> list[dict] | None:
    """Split roman/lettered subparts from a long-answer text; return list or None."""
    matches = list(_LA_SUBPART_RE.finditer(text))
    if not matches:
        return None
    subparts = []
    for idx, m in enumerate(matches):
        label = m.group(1).lower()
        start = m.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        content_text = text[start:end].strip()
        if content_text:
            subparts.append(
                {
                    "label": label,
                    "marks": 0,
                    "content": [{"type": "paragraph", "text": content_text}],
                }
            )
    return subparts if subparts else None


def _classify_qtype(raw_question: dict, section: str) -> str:
    """Return qtype string. Detected structure wins; section default fallback."""
    text = raw_question.get("text", "")
    if _parse_assertion_reason(text) is not None:
        return "assertion_reason"
    if _parse_internal_choice(text) is not None:
        return "internal_choice"
    if _parse_case_based(text) is not None:
        return "case_based"
    return SECTION_DEFAULT_QTYPE.get(section, "short_answer")


def _compute_parse_quality(raw_question: dict, classified_qtype: str) -> str:
    """Return clean/partial/broken based on how well structure matches qtype."""
    text = raw_question.get("text", "")
    content = raw_question.get("content", {})

    if classified_qtype == "assertion_reason":
        if content.get("assertion") and content.get("reason"):
            return "clean"
        return "broken"

    if classified_qtype == "case_based":
        if content.get("passage") and len(content.get("subparts", [])) >= 2:
            return "clean"
        return "partial"

    if classified_qtype == "internal_choice":
        choices = content.get("choices", [])
        if choices and len(choices[0].get("options", [])) == 2:
            return "clean"
        return "broken"

    if classified_qtype == "mcq":
        options = raw_question.get("options", [])
        if len(options) == 4:
            return "clean"
        return "partial" if options else "broken"

    # short_answer, long_answer, very_short_answer
    if text.strip():
        return "clean"
    return "broken"


def segment_questions(text: str) -> list[dict]:
    """Split cleaned text into raw question dicts.

    Returns list of dicts with keys: section, qtype, marks, text, options,
    content, parse_quality. Does NOT contact any external service.
    """
    section_blocks: list[tuple[str, str]] = []
    current_section: str | None = None
    current_lines: list[str] = []

    for line in text.splitlines():
        m = _SECTION_RE.search(line)
        if m:
            if current_section is not None:
                section_blocks.append((current_section, "\n".join(current_lines)))
            current_section = m.group(1).upper()
            current_lines = []
        else:
            current_lines.append(line)

    if current_section is not None:
        section_blocks.append((current_section, "\n".join(current_lines)))

    questions: list[dict] = []

    for section_code, block in section_blocks:
        default_marks = SECTION_DEFAULT_MARKS.get(section_code, 1)

        splits = list(_QNUM_RE.finditer(block))
        for i, match in enumerate(splits):
            start = match.end()
            end = splits[i + 1].start() if i + 1 < len(splits) else len(block)
            raw = block[start:end].strip()

            if not raw or len(raw) < 8:
                continue

            marks = default_marks
            m_match = _MARKS_RE.search(raw)
            if m_match:
                marks = int(m_match.group(1) or m_match.group(2))
                raw = _MARKS_RE.sub("", raw).strip()

            # Classify on unmodified raw text so AR detection sees full structure.
            qtype = _classify_qtype({"text": raw, "options": []}, section_code)

            options: list[dict] = []
            if qtype == "mcq" and section_code == "A":
                options, raw = _parse_options(raw)

            raw_q: dict = {"text": raw, "options": options}

            content: dict = {}
            if qtype == "assertion_reason":
                content = _parse_assertion_reason(raw) or {}
            elif qtype == "internal_choice":
                content = _parse_internal_choice(raw) or {}
            elif qtype == "case_based":
                content = _parse_case_based(raw) or {}
            elif qtype == "mcq":
                content = {
                    "stem": [{"type": "paragraph", "text": raw}],
                    "options": [
                        {
                            "label": o["label"],
                            "content": [{"type": "paragraph", "text": o["text"]}],
                        }
                        for o in options
                    ],
                }
            else:
                subparts = _parse_long_answer_subparts(raw)
                if subparts:
                    content = {"stem": [], "subparts": subparts}
                else:
                    content = {"stem": [{"type": "paragraph", "text": raw}]}

            raw_q["content"] = content
            parse_quality = _compute_parse_quality(raw_q, qtype)

            questions.append(
                {
                    "section": section_code,
                    "qtype": qtype,
                    "marks": marks,
                    "text": raw,
                    "options": options,
                    "content": content,
                    "parse_quality": parse_quality,
                }
            )

    return questions


# ---------------------------------------------------------------------------
# Verification — deterministic guardrails on segmenter output (ADR-0003)
# ---------------------------------------------------------------------------

_FIDELITY_THRESHOLD = 0.9


def _normalize_ws(text: str) -> str:
    """Lowercase and collapse all whitespace to single spaces, for span matching."""
    return re.sub(r"\s+", " ", text.lower()).strip()


def _source_offset(norm_source: str, text: str) -> int | None:
    """Offset of `text` in the normalised source, or None if not faithfully present.

    Exact substring first; falls back to the longest common block and accepts it
    only if it covers >= `_FIDELITY_THRESHOLD` of the candidate text. Returns the
    source offset so callers can also check reading order.
    """
    norm_text = _normalize_ws(text)
    if not norm_text:
        return None
    idx = norm_source.find(norm_text)
    if idx != -1:
        return idx
    matcher = difflib.SequenceMatcher(None, norm_source, norm_text, autojunk=False)
    block = matcher.find_longest_match(0, len(norm_source), 0, len(norm_text))
    if block.size / len(norm_text) >= _FIDELITY_THRESHOLD:
        return block.a
    return None


def _option_texts(question: dict) -> list[str]:
    """Flat list of an MCQ/AR question's option strings, in emitted order."""
    if question.get("options"):
        return [o.get("text", "") for o in question["options"]]
    texts: list[str] = []
    for opt in question.get("content", {}).get("options", []):
        body = opt.get("content", [])
        texts.append(body[0].get("text", "") if body else "")
    return texts


def _options_in_source_order(question: dict, norm_source: str) -> bool:
    """True if every option text is faithfully present, in source order."""
    offsets: list[int] = []
    for text in _option_texts(question):
        offset = _source_offset(norm_source, text)
        if offset is None:
            return False
        offsets.append(offset)
    return offsets == sorted(offsets)


def _verify(questions: list[dict], source_text: str) -> list[dict]:
    """Score segmenter output against the source text; set `parse_quality` (ADR-0003).

    Three deterministic checks. A failure forces the row to `broken`, except a
    coverage mismatch which only degrades a `clean` row to `partial` (we can't
    pinpoint which row is wrong):

      * fidelity — the question's text is faithfully present in the source.
      * order    — questions appear in source reading order, and MCQ/AR options
                   appear in source order within the question.
      * coverage — emitted question count matches the source's question-number
                   anchors.
    """
    norm_source = _normalize_ws(source_text)
    anchor_count = len(_QNUM_RE.findall(source_text))
    coverage_ok = anchor_count == 0 or len(questions) == anchor_count

    verified: list[dict] = []
    prev_offset = -1
    for q in questions:
        qtype = q.get("qtype", "")
        quality = q.get("parse_quality") or _compute_parse_quality(q, qtype)

        offset = _source_offset(norm_source, q.get("text", ""))
        if offset is None:
            quality = "broken"  # fidelity: invented or altered text
        else:
            if offset < prev_offset:
                quality = "broken"  # order: question out of reading order
            else:
                prev_offset = offset
            if quality != "broken" and qtype in ("mcq", "assertion_reason"):
                if not _options_in_source_order(q, norm_source):
                    quality = "broken"  # swapped/invented option labels

        if not coverage_ok and quality == "clean":
            quality = "partial"

        verified.append({**q, "parse_quality": quality})

    return verified


# ---------------------------------------------------------------------------
# Seams
# ---------------------------------------------------------------------------


class Parser(Protocol):
    def parse(self, pdf_bytes: bytes) -> str: ...

    def parse_pages(self, pdf_bytes: bytes) -> list[str]: ...


class Segmenter(Protocol):
    """Splits cleaned paper text into raw question dicts.

    Each dict carries: section, qtype, marks, text, options, content. The
    coordinator runs `_verify` over the result to set `parse_quality`.
    """

    def segment(self, text: str) -> list[dict]: ...


class Tagger(Protocol):
    def tag(self, raw_questions: list[dict], chapters: list[Chapter]) -> list[dict]: ...


class DiagramExtractor(Protocol):
    """One entry per question: cropped image bytes, or None if no image found."""

    def extract(
        self, pdf_bytes: bytes, raw_questions: list[dict]
    ) -> list[bytes | None]: ...


class AnswerSource(Protocol):
    """Parses an answer/marking-scheme PDF into `{question_number: answer_text}`."""

    def answers(self, pdf_bytes: bytes) -> dict[int, str]: ...


class PdfplumberParser:
    """Default Parser — extracts text from each PDF page via pdfplumber."""

    def parse(self, pdf_bytes: bytes) -> str:
        return "\n".join(self.parse_pages(pdf_bytes))

    def parse_pages(self, pdf_bytes: bytes) -> list[str]:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            return [page.extract_text() or "" for page in pdf.pages]


class RegexSegmenter:
    """Deterministic Segmenter — the legacy `segment_questions` rules.

    Kept as a fallback for when the LLM call fails, and so existing rule-based
    behaviour stays exercised.
    """

    def segment(self, text: str) -> list[dict]:
        return segment_questions(text)


_SEGMENT_PROMPT = (
    "You are segmenting a CBSE Class 10 Science question paper into individual "
    "questions for a question bank.\n\n"
    "Return a JSON array. One object per question, in the order they appear, with:\n"
    "  section  — the paper section letter A-E the question falls under\n"
    "  qtype    — one of: mcq, assertion_reason, very_short_answer, short_answer, "
    "long_answer, case_based, internal_choice\n"
    "  marks    — integer marks for the question\n"
    "  text     — the question stem, copied VERBATIM from the paper (do not "
    "paraphrase, correct, or complete it; omit option labels from the stem)\n"
    "  options  — for mcq/assertion_reason: array of {label, text} with text "
    "copied verbatim; otherwise []\n"
    "  content  — structured content matching the question type:\n"
    "    mcq:              {stem:[{type:'paragraph',text}], options:[{label, "
    "content:[{type:'paragraph',text}]}]}\n"
    "    assertion_reason: {assertion:[{type:'paragraph',text}], reason:"
    "[{type:'paragraph',text}], options:[{label, content:[...]}]}\n"
    "    case_based:       {passage:[{type:'paragraph',text}], subparts:[{label, "
    "marks, content:[{type:'paragraph',text}]}]}\n"
    "    internal_choice:  {choices:[{displayStyle:'or', chooseCount:1, options:"
    "[{label, content:[{type:'paragraph',text}]}]}]}\n"
    "    short/long/very_short_answer: {stem:[{type:'paragraph',text}]}\n\n"
    "Copy all text verbatim from the paper. Never invent options, subparts, or "
    "wording. Respond with only the JSON array.\n\n"
    "Paper text:\n"
)


def _coerce_segment(obj: dict) -> dict:
    """Normalise one LLM-emitted question object to the segmenter dict shape."""
    try:
        marks = int(obj.get("marks"))
    except (TypeError, ValueError):
        marks = SECTION_DEFAULT_MARKS.get(str(obj.get("section", "")).upper(), 1)
    return {
        "section": str(obj.get("section", "")).upper(),
        "qtype": obj.get("qtype", "short_answer"),
        "marks": marks,
        "text": obj.get("text", ""),
        "options": obj.get("options", []) or [],
        "content": obj.get("content", {}) or {},
    }


class LLMSegmenter:
    """Default Segmenter — an LLM splits, classifies, and structures the paper text.

    Provider-agnostic via `LLMClient`. Falls back to `RegexSegmenter` when the
    call fails or the response can't be parsed, so a bad LLM round-trip degrades
    to the deterministic rules rather than dropping the whole paper.
    """

    def __init__(
        self, client: LLMClient | None = None, fallback: Segmenter | None = None
    ):
        self.client = client or make_llm_client()
        self.fallback = fallback or RegexSegmenter()

    def segment(self, text: str) -> list[dict]:
        if not text.strip():
            return []
        try:
            response = self.client.complete(
                _SEGMENT_PROMPT + text, max_tokens=4096
            ).strip()
            response = re.sub(r"^```\w*\n?", "", response)
            response = re.sub(r"\n?```$", "", response)
            data = json.loads(response)
        except Exception:
            return self.fallback.segment(text)
        if not isinstance(data, list):
            return self.fallback.segment(text)
        return [_coerce_segment(obj) for obj in data if isinstance(obj, dict)]


class PdfplumberDiagramExtractor:
    """Crops embedded images from a PDF and associates them with questions.

    Association heuristic: for each image on a page, find the question whose
    text appears nearest above the image's top edge. Questions explicitly
    mentioning 'Fig.' / 'diagram' are also flagged regardless of detected images.
    """

    def extract(
        self, pdf_bytes: bytes, raw_questions: list[dict]
    ) -> list[bytes | None]:
        if not raw_questions:
            return []

        results: list[bytes | None] = [None] * len(raw_questions)
        try:
            self._crop_images_into(pdf_bytes, raw_questions, results)
        except Exception:
            # Non-PDF bytes or rendering failure — degrade to "no images extracted".
            # The coordinator still flags has_diagram via _mentions_diagram on the text.
            pass
        return results

    def _crop_images_into(
        self,
        pdf_bytes: bytes,
        raw_questions: list[dict],
        results: list[bytes | None],
    ) -> None:
        question_texts = [q["text"] for q in raw_questions]
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            # Build per-page flat text so we can locate questions by page.
            page_texts = [page.extract_text() or "" for page in pdf.pages]
            # For each question, determine its page by text search.
            question_pages: list[int] = []
            for qt in question_texts:
                snippet = qt[:60]
                page_num = next(
                    (i for i, pt in enumerate(page_texts) if snippet in pt),
                    -1,
                )
                question_pages.append(page_num)

            for page_idx, page in enumerate(pdf.pages):
                page_images = page.images
                if not page_images:
                    continue

                # Indices of questions on this page, in document order.
                qs_on_page = [
                    qi for qi, pg in enumerate(question_pages) if pg == page_idx
                ]
                if not qs_on_page:
                    continue

                # For each image, assign to the last question whose text bbox
                # top is above the image's top (i.e., question precedes image).
                page_words = page.extract_words()
                for img in page_images:
                    img_top = img.get("top", img.get("y0", 0))
                    img_bytes = self._crop_image(page, img)
                    if img_bytes is None:
                        continue

                    # Find question on this page whose text appears above img_top.
                    best_qi: int | None = None
                    for qi in qs_on_page:
                        snippet = question_texts[qi][:40]
                        word_tops = [
                            w["top"]
                            for w in page_words
                            if snippet[:10] in w.get("text", "")
                        ]
                        q_top = min(word_tops) if word_tops else float("inf")
                        if q_top <= img_top:
                            best_qi = qi
                    if best_qi is not None and results[best_qi] is None:
                        results[best_qi] = img_bytes

    @staticmethod
    def _crop_image(page: pdfplumber.page.Page, img: dict) -> bytes | None:
        """Render the image bbox as PNG bytes. Returns None on failure."""
        try:
            bbox = (img["x0"], img["top"], img["x1"], img["bottom"])
            cropped = page.crop(bbox)
            pil_img = cropped.to_image(resolution=150).original
            buf = io.BytesIO()
            pil_img.save(buf, format="PNG")
            return buf.getvalue()
        except Exception:
            return None


class LLMTagger:
    """Default Tagger — batches questions to an LLM for chapter/level tagging.

    Provider-agnostic: takes any `LLMClient`. Defaults to the one
    `make_llm_client()` returns (driven by `LLM_PROVIDER` env var).
    """

    def __init__(self, client: LLMClient | None = None):
        self.client = client or make_llm_client()

    def tag(self, raw_questions: list[dict], chapters: list[Chapter]) -> list[dict]:
        if not raw_questions:
            return []

        chapter_list = [{"slug": c.slug, "name": c.name} for c in chapters]
        tagged = list(raw_questions)

        for batch_start in range(0, len(raw_questions), _TAG_BATCH):
            batch = raw_questions[batch_start : batch_start + _TAG_BATCH]
            prompt = (
                "You are tagging CBSE Class 10 Science questions "
                "for a question bank.\n\n"
                f"Chapters:\n{json.dumps(chapter_list, indent=2)}\n\n"
                "Cognitive levels: R (Remember), U (Understand), "
                "Ap (Apply), An (Analyse)\n\n"
                "For each question return a JSON array of objects with:\n"
                "  index        — same as input\n"
                "  chapter_slug — closest chapter slug, or null if unclear\n"
                "  cognitive_level — one of R / U / Ap / An\n\n"
                "Questions:\n"
                + json.dumps(
                    [
                        {"index": batch_start + i, "text": q["text"]}
                        for i, q in enumerate(batch)
                    ],
                    indent=2,
                )
                + "\n\nRespond with only the JSON array."
            )
            response_text = self.client.complete(prompt, max_tokens=2048).strip()
            response_text = re.sub(r"^```\w*\n?", "", response_text)
            response_text = re.sub(r"\n?```$", "", response_text)

            for tag in json.loads(response_text):
                idx = tag["index"]
                tagged[idx] = {
                    **tagged[idx],
                    "chapter_slug": tag.get("chapter_slug"),
                    "cognitive_level": tag.get("cognitive_level", "R"),
                }

        return tagged


class MarkingSchemeAnswerSource:
    """Default AnswerSource — parses CBSE marking-scheme PDFs.

    Looks for lines like ``1. <answer>`` / ``Q1) <answer>`` and merges
    contiguous continuation lines (and ``Ans.`` headers) into the most
    recently seen question number.
    """

    def answers(self, pdf_bytes: bytes) -> dict[int, str]:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)

        result: dict[int, str] = {}
        current_qnum: int | None = None
        current_lines: list[str] = []

        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue

            ans_header = _SCHEME_ANS_HEADER_RE.match(line)
            if ans_header and current_qnum is not None:
                current_lines.append(ans_header.group(1).strip())
                continue

            num_match = _SCHEME_ANS_LINE_RE.match(line)
            if num_match:
                if current_qnum is not None:
                    result[current_qnum] = " ".join(current_lines).strip()
                current_qnum = int(num_match.group(1))
                current_lines = [num_match.group(2).strip()]
            elif current_qnum is not None:
                current_lines.append(line)

        if current_qnum is not None:
            result[current_qnum] = " ".join(current_lines).strip()

        return result


# ---------------------------------------------------------------------------
# Coordinator
# ---------------------------------------------------------------------------


@dataclass
class IngestResult:
    created: int
    skipped_duplicates: int = 0


class Ingestor:
    """Pipeline coordinator. All four adapters are injectable.

    The default constructor wires the production adapters; tests pass stubs.
    """

    def __init__(
        self,
        parser: Parser | None = None,
        segmenter: Segmenter | None = None,
        tagger: Tagger | None = None,
        extractor: DiagramExtractor | None = None,
        answer_source: AnswerSource | None = None,
    ):
        self.parser = parser or PdfplumberParser()
        self.segmenter = segmenter or LLMSegmenter()
        self.tagger = tagger or LLMTagger()
        self.extractor = extractor or PdfplumberDiagramExtractor()
        self.answer_source = answer_source or MarkingSchemeAnswerSource()

    def ingest(self, pdf_bytes: bytes) -> IngestResult:
        raw_text = self.parser.parse(pdf_bytes)
        clean_text = strip_hindi(raw_text)
        raw_questions = self.segmenter.segment(clean_text)
        if not raw_questions:
            return IngestResult(created=0)

        # Guardrail: score LLM output against the source text before trusting it.
        raw_questions = _verify(raw_questions, clean_text)

        # De-duplication: skip questions already in the bank AND repeats
        # within this PDF.
        all_fingerprints = [_fingerprint(q["text"]) for q in raw_questions]
        seen = set(
            Question.objects.filter(source_hash__in=all_fingerprints).values_list(
                "source_hash", flat=True
            )
        )
        unique_indices: list[int] = []
        for i, fp in enumerate(all_fingerprints):
            if fp in seen:
                continue
            seen.add(fp)
            unique_indices.append(i)
        skipped = len(raw_questions) - len(unique_indices)
        raw_questions = [raw_questions[i] for i in unique_indices]
        fingerprints = [all_fingerprints[i] for i in unique_indices]

        if not raw_questions:
            return IngestResult(created=0, skipped_duplicates=skipped)

        # Diagram extraction (best-effort; failures produce None entries).
        diagram_bytes_list = self.extractor.extract(pdf_bytes, raw_questions)

        chapters = list(Chapter.objects.all())
        tagged = self.tagger.tag(raw_questions, chapters)
        chapter_by_slug = {c.slug: c for c in chapters}
        created = self._persist(
            tagged, fingerprints, diagram_bytes_list, chapter_by_slug
        )
        return IngestResult(created=created, skipped_duplicates=skipped)

    def apply_answers(self, answer_pdf_bytes: bytes) -> int:
        """Parse an answer/marking-scheme PDF and fill in ``Question.answer``.

        Match strategy: the n-th answer in the parsed scheme assigns to the
        n-th unverified Question row ordered by id. See module docstring for
        why this is sufficient for CBSE marking schemes today.
        """
        scheme = self.answer_source.answers(answer_pdf_bytes)
        if not scheme:
            return 0

        questions = list(Question.objects.filter(verified=False).order_by("id"))
        updated = 0
        for q_num, answer_text in scheme.items():
            idx = q_num - 1
            if 0 <= idx < len(questions) and answer_text:
                q = questions[idx]
                q.answer = answer_text
                q.save(update_fields=["answer"])
                updated += 1
        return updated

    @staticmethod
    def _persist(
        tagged: list[dict],
        fingerprints: list[str],
        diagram_bytes_list: list[bytes | None],
        chapter_by_slug: dict[str, Chapter],
    ) -> int:
        from django.core.files.base import ContentFile

        rows: list[Question] = []
        for i, q in enumerate(tagged):
            image_bytes = diagram_bytes_list[i] if i < len(diagram_bytes_list) else None
            has_diagram = image_bytes is not None or _mentions_diagram(q["text"])

            row = Question(
                chapter=chapter_by_slug.get(q.get("chapter_slug")),
                section=q["section"],
                qtype=q["qtype"],
                marks=q["marks"],
                cognitive_level=q.get("cognitive_level", CognitiveLevel.REMEMBER),
                text=q["text"],
                options=q.get("options", []),
                content=q.get("content", {}),
                parse_quality=q.get("parse_quality", "partial"),
                answer="",
                verified=False,
                has_diagram=has_diagram,
                is_numerical=_detect_numerical(q["text"]),
                source_hash=fingerprints[i],
            )
            if image_bytes:
                row.diagram.save(
                    f"q_{fingerprints[i][:8]}.png",
                    ContentFile(image_bytes),
                    save=False,
                )
            rows.append(row)

        Question.objects.bulk_create(rows)
        return len(rows)
