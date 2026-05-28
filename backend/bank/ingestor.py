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
    "A": "MCQ",
    "B": "VSA",
    "C": "SA",
    "D": "LA",
    "E": "CASE",
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


def segment_questions(text: str) -> list[dict]:
    """Split cleaned text into raw question dicts.

    Returns list of dicts with keys: section, qtype, marks, text, options.
    Does NOT contact any external service.
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
        default_qtype = SECTION_DEFAULT_QTYPE.get(section_code, "SA")

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

            options: list[dict] = []
            if section_code == "A":
                options, raw = _parse_options(raw)

            questions.append(
                {
                    "section": section_code,
                    "qtype": default_qtype,
                    "marks": marks,
                    "text": raw,
                    "options": options,
                }
            )

    return questions


# ---------------------------------------------------------------------------
# Seams
# ---------------------------------------------------------------------------


class Parser(Protocol):
    def parse(self, pdf_bytes: bytes) -> str: ...

    def parse_pages(self, pdf_bytes: bytes) -> list[str]: ...


class Tagger(Protocol):
    def tag(self, raw_questions: list[dict], chapters: list[Chapter]) -> list[dict]: ...


class DiagramExtractor(Protocol):
    """Returns one entry per question: cropped image bytes, or None if no image was found."""

    def extract(self, pdf_bytes: bytes, raw_questions: list[dict]) -> list[bytes | None]: ...


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


class PdfplumberDiagramExtractor:
    """Crops embedded images from a PDF and associates them with questions.

    Association heuristic: for each image on a page, find the question whose
    text appears nearest above the image's top edge. Questions explicitly
    mentioning 'Fig.' / 'diagram' are also flagged regardless of detected images.
    """

    def extract(self, pdf_bytes: bytes, raw_questions: list[dict]) -> list[bytes | None]:
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
                qs_on_page = [qi for qi, pg in enumerate(question_pages) if pg == page_idx]
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
                            w["top"] for w in page_words if snippet[:10] in w.get("text", "")
                        ]
                        q_top = min(word_tops) if word_tops else float("inf")
                        if q_top <= img_top:
                            best_qi = qi
                    if best_qi is not None and results[best_qi] is None:
                        results[best_qi] = img_bytes

    @staticmethod
    def _crop_image(page: "pdfplumber.page.Page", img: dict) -> bytes | None:
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
                "You are tagging CBSE Class 10 Science questions for a question bank.\n\n"
                f"Chapters:\n{json.dumps(chapter_list, indent=2)}\n\n"
                "Cognitive levels: R (Remember), U (Understand), Ap (Apply), An (Analyse)\n\n"
                "For each question return a JSON array of objects with:\n"
                "  index        — same as input\n"
                "  chapter_slug — closest chapter slug, or null if unclear\n"
                "  cognitive_level — one of R / U / Ap / An\n\n"
                "Questions:\n"
                + json.dumps(
                    [{"index": batch_start + i, "text": q["text"]} for i, q in enumerate(batch)],
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
        tagger: Tagger | None = None,
        extractor: DiagramExtractor | None = None,
        answer_source: AnswerSource | None = None,
    ):
        self.parser = parser or PdfplumberParser()
        self.tagger = tagger or LLMTagger()
        self.extractor = extractor or PdfplumberDiagramExtractor()
        self.answer_source = answer_source or MarkingSchemeAnswerSource()

    def ingest(self, pdf_bytes: bytes) -> IngestResult:
        raw_text = self.parser.parse(pdf_bytes)
        clean_text = strip_hindi(raw_text)
        raw_questions = segment_questions(clean_text)
        if not raw_questions:
            return IngestResult(created=0)

        # De-duplication: skip questions already in the bank AND repeats within this PDF.
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
        created = self._persist(tagged, fingerprints, diagram_bytes_list, chapter_by_slug)
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
