"""Ingestion pipeline: extract questions from a CBSE past-paper PDF via Gemini.

`Ingestor` is the coordinator. It runs the pipeline and persists Question rows
(verified=False). Two seams are injected as adapters:

* `Extractor` — sends the source PDF straight to a multimodal LLM and returns
                structured, tagged question dicts. Default: `GeminiExtractor`.
* `DiagramCropper` — crops the Extractor's figure boxes into media assets and
                rewrites the content. Default: `PyMuPdfCropper` (see
                `bank.diagram_cropper`).

The PDF goes to the model unchanged: no text extraction, no regex segmentation,
no fidelity guardrail (see ADR-0004). The model does, in one pass per section,
English-only filtering (discard the Hindi column), segmentation, type
classification, `content` region structuring, and chapter/level/topic tagging.
The human verification gate (ADR-0002) is the backstop — rows land
`verified=False` and only reviewed rows reach the picker.

The structural `parse_quality` self-assessment lives in `bank.question_shape`
(`compute_parse_quality`); the Content tree-walk used to flag `has_diagram` lives
in `bank.content`. Pure text predicates (`_detect_numerical`,
`_mentions_diagram`) stay module-level. Tests inject stub adapters into
Ingestor — no module-level patching.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ai_services.llm import LLMClient, make_llm_client

from . import content as content_mod
from .diagram_cropper import DiagramCropper, PyMuPdfCropper
from .models import Chapter, CognitiveLevel, Question
from .question_shape import compute_parse_quality

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

# Per-section default marks — used as a fallback when the model omits `marks`.
SECTION_DEFAULT_MARKS: dict[str, int] = {"A": 1, "B": 2, "C": 3, "D": 5, "E": 4}


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


_CBSE_TOKEN_RE = re.compile(r"[_\-]")
_YEAR_RE = re.compile(r"(\d{4})$")


def _parse_source_filename(path: Path) -> dict:
    """Parse a CBSE paper PDF path into source provenance fields.

    Derives year from the parent directory name (e.g. ``science_2024`` → 2024).
    Stem tokens are split on ``_`` and ``-``; numeric tokens are joined with
    ``-``, the trailing alphabetic token (subject label) is appended with a
    space, and the year is appended last.

    Examples::

        science_2024/31_1_1_Science.pdf → source_name "31-1-1 Science 2024"
        science_2025/31-2-1.pdf         → source_name "31-2-1 2025"
    """
    file_name = path.name
    stem = path.stem

    year_match = _YEAR_RE.search(path.parent.name)
    year = year_match.group(1) if year_match else ""

    tokens = _CBSE_TOKEN_RE.split(stem)
    numeric_tokens = [t for t in tokens if t.isdigit()]
    alpha_tokens = [t for t in tokens if not t.isdigit() and t]

    parts = ["-".join(numeric_tokens)] if numeric_tokens else []
    parts += alpha_tokens
    if year:
        parts.append(year)
    source_name = " ".join(parts)

    return {
        "source_type": "previous_year_paper",
        "source_name": source_name,
        "source_file_name": file_name,
    }


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


# ---------------------------------------------------------------------------
# Extractor seam
# ---------------------------------------------------------------------------


class Extractor(Protocol):
    """Turns PDF bytes into structured, tagged question dicts.

    Each dict carries: ``section``, ``qtype``, ``marks``, ``text``, ``options``,
    ``content`` (contract §9 region shape), ``chapter_slug``, ``cognitive_level``,
    ``topic_names``, ``primary_form``, and ``figures`` (bounding boxes the
    coordinator crops into assets). The coordinator sets ``parse_quality``.
    """

    def extract(self, pdf_bytes: bytes) -> list[dict]: ...


_PRIMARY_FORMS = ("none", "diagram_based", "table_based")

# Content regions a figure may anchor to: item-array + labelled regions (the
# model's `label` picks the option/subpart). `choices` nesting is out of scope
# (#77). Region names are owned by `bank.content`.
_FIGURE_REGIONS = content_mod.ITEM_REGIONS + content_mod.LABELLED_REGIONS


def _coerce_topic_names(value) -> list[str]:
    """Normalise a model ``topic_names`` value to a clean list of non-empty strings."""
    if not isinstance(value, list):
        return []
    return [s.strip() for s in value if isinstance(s, str) and s.strip()]


def _coerce_primary_form(value) -> str:
    """Clamp a model ``primary_form`` value to the known set; default ``none``."""
    return value if value in _PRIMARY_FORMS else "none"


# Provider-enforced response schema (google-genai dict form). Top-level is an
# object so `LLMClient.extract` returns a dict; questions are schema-valid by
# construction. Tables (`rows`) are out of scope this slice — they fall back to
# rawText (see #77 for figure crops / richer content).
_CONTENT_ITEM = {
    "type": "OBJECT",
    "properties": {
        "type": {"type": "STRING"},
        "text": {"type": "STRING"},
        "latex": {"type": "STRING"},
    },
    "required": ["type"],
}
_CONTENT_ITEMS = {"type": "ARRAY", "items": _CONTENT_ITEM}
# ChoiceOption and SubQuestion share a shape: {label, marks?, content[]}.
_LABELLED_CONTENT = {
    "type": "OBJECT",
    "properties": {
        "label": {"type": "STRING"},
        "marks": {"type": "INTEGER"},
        "content": _CONTENT_ITEMS,
    },
    "required": ["label", "content"],
}
_CHOICE_GROUP = {
    "type": "OBJECT",
    "properties": {
        "displayStyle": {"type": "STRING"},
        "chooseCount": {"type": "INTEGER"},
        "options": {"type": "ARRAY", "items": _LABELLED_CONTENT},
    },
    "required": ["options"],
}
_FLAT_OPTION = {
    "type": "OBJECT",
    "properties": {
        "label": {"type": "STRING"},
        "text": {"type": "STRING"},
    },
    "required": ["label", "text"],
}
_QUESTION_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "questions": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "section": {"type": "STRING", "enum": ["A", "B", "C", "D", "E"]},
                    "qtype": {
                        "type": "STRING",
                        "enum": [
                            "mcq",
                            "assertion_reason",
                            "very_short_answer",
                            "short_answer",
                            "long_answer",
                            "case_based",
                            "internal_choice",
                        ],
                    },
                    "marks": {"type": "INTEGER"},
                    "rawText": {"type": "STRING"},
                    "options": {"type": "ARRAY", "items": _FLAT_OPTION},
                    "content": {
                        "type": "OBJECT",
                        "properties": {
                            "stem": _CONTENT_ITEMS,
                            "assertion": _CONTENT_ITEMS,
                            "reason": _CONTENT_ITEMS,
                            "passage": _CONTENT_ITEMS,
                            "options": {"type": "ARRAY", "items": _LABELLED_CONTENT},
                            "subparts": {"type": "ARRAY", "items": _LABELLED_CONTENT},
                            "choices": {"type": "ARRAY", "items": _CHOICE_GROUP},
                        },
                    },
                    "chapter_slug": {"type": "STRING"},
                    "cognitive_level": {
                        "type": "STRING",
                        "enum": ["R", "U", "Ap", "An"],
                    },
                    "topic_names": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "primary_form": {
                        "type": "STRING",
                        "enum": list(_PRIMARY_FORMS),
                    },
                    # Figure bounding boxes for deterministic PyMuPDF cropping
                    # (#77). bbox is [x0, y0, x1, y1] normalized to [0, 1],
                    # top-left origin; page is 1-based.
                    "figures": {
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "page": {"type": "INTEGER"},
                                "bbox": {
                                    "type": "ARRAY",
                                    "items": {"type": "NUMBER"},
                                },
                                "region": {
                                    "type": "STRING",
                                    "enum": list(_FIGURE_REGIONS),
                                },
                                "label": {"type": "STRING"},
                                "caption": {"type": "STRING"},
                            },
                            "required": ["page", "bbox", "region"],
                        },
                    },
                },
                "required": ["section", "qtype", "marks", "rawText", "content"],
            },
        }
    },
    "required": ["questions"],
}

_SECTIONS = ("A", "B", "C", "D", "E")
_SECTION_LABELS = {
    "A": "Section A (objective: MCQ / assertion-reason, 1 mark each)",
    "B": "Section B (very short answer, 2 marks each)",
    "C": "Section C (short answer, 3 marks each)",
    "D": "Section D (long answer, 5 marks each)",
    "E": "Section E (case-based, 4 marks each)",
}


def _section_prompt(section: str) -> str:
    """Build the per-section extraction prompt (English-only, verbatim)."""
    return (
        "You are extracting questions from a CBSE Class 10 Science board paper PDF "
        "into a question bank.\n\n"
        f"Extract ONLY the questions in {_SECTION_LABELS[section]}. Ignore every "
        "other section, the cover page, the general instructions, and any marking "
        "scheme. If this section is absent, return an empty list.\n\n"
        "ENGLISH ONLY: these papers are bilingual — a Hindi (Devanagari) column or "
        "block sits alongside the English. Keep the English only; discard the Hindi "
        "entirely and do NOT translate it. No Devanagari characters in the output.\n\n"
        "Copy each question VERBATIM from the English text — never paraphrase, "
        "correct, complete, or summarise it.\n\n"
        "Per question return:\n"
        f"  section — always {section}.\n"
        "  qtype — one of: mcq, assertion_reason, very_short_answer, short_answer, "
        "long_answer, case_based, internal_choice.\n"
        "  marks — integer marks for the question.\n"
        "  rawText — the stem copied verbatim, WITHOUT any visible marks "
        "(no '[1]', '(2 marks)', trailing mark digits) and WITHOUT option labels.\n"
        "  options — for mcq/assertion_reason: [{label, text}] verbatim; else [].\n"
        "  content — keyed by region, include only the regions the type uses:\n"
        "    stem / assertion / reason / passage: arrays of {type, text, latex?} "
        "where type is 'paragraph', 'equation', or 'image_placeholder'.\n"
        "    options / subparts: [{label, marks?, content:[item, ...]}].\n"
        "    choices (internal_choice): [{displayStyle:'or', chooseCount, "
        "options:[{label, content:[item, ...]}]}].\n"
        "  chapter_slug — closest CBSE Cl.10 Science chapter slug, or null if unsure.\n"
        "  cognitive_level — one of R, U, Ap, An.\n"
        "  topic_names — short topic strings within the chapter; [] if none.\n"
        "  primary_form — one of none, diagram_based, table_based.\n"
        "  figures — bounding boxes of any diagrams the question depends on, for "
        "deterministic cropping. [] if none. Each: {page, bbox, region, label?, "
        "caption?} where page is 1-based, bbox is [x0, y0, x1, y1] normalized to "
        "[0, 1] with the page top-left as origin, region is the content region the "
        "figure belongs to (stem / assertion / reason / passage / options / "
        "subparts), and label names the option/subpart for options/subparts.\n\n"
        "If a question depends on a figure or diagram, put a single "
        "{type:'image_placeholder', text:'<short description>'} item in the region "
        "where the figure appears AND add a matching entry to figures (same region "
        "and, for an option/subpart, the same label). The crop is made from the "
        "box; the placeholder is the anchor. Never invent pixels, options, or "
        "subparts."
    )


def _coerce_figures(value) -> list[dict]:
    """Normalise a model ``figures`` value to clean, croppable box dicts.

    Keeps only entries with a 1-based int ``page``, a ``bbox`` of exactly four
    numbers forming a non-empty rectangle once clamped to ``[0, 1]``, and a known
    ``region``. ``label`` is coerced to a string. Anything malformed is dropped
    silently — the question's ``image_placeholder`` simply stays (fail-soft per
    ADR-0004; bad localisation is caught at human review).
    """
    if not isinstance(value, list):
        return []
    figures: list[dict] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        page = item.get("page")
        if not isinstance(page, int) or isinstance(page, bool) or page < 1:
            continue
        bbox = item.get("bbox")
        if not isinstance(bbox, list) or len(bbox) != 4:
            continue
        if not all(
            isinstance(n, (int, float)) and not isinstance(n, bool) for n in bbox
        ):
            continue
        x0, y0, x1, y1 = (min(1.0, max(0.0, float(n))) for n in bbox)
        if x0 >= x1 or y0 >= y1:
            continue
        region = item.get("region")
        if region not in _FIGURE_REGIONS:
            continue
        figure = {"page": page, "bbox": [x0, y0, x1, y1], "region": region}
        label = item.get("label")
        if isinstance(label, str) and label.strip():
            figure["label"] = label.strip()
        caption = item.get("caption")
        if isinstance(caption, str) and caption.strip():
            figure["caption"] = caption.strip()
        figures.append(figure)
    return figures


def _coerce_question(obj: dict, section: str) -> dict:
    """Normalise one model-emitted question object to the coordinator dict shape."""
    try:
        marks = int(obj.get("marks"))
    except (TypeError, ValueError):
        marks = SECTION_DEFAULT_MARKS.get(section, 1)
    return {
        "section": section,
        "qtype": obj.get("qtype", "short_answer"),
        "marks": marks,
        "text": obj.get("rawText", "") or "",
        "options": obj.get("options", []) or [],
        "content": obj.get("content", {}) or {},
        "chapter_slug": obj.get("chapter_slug"),
        "cognitive_level": obj.get("cognitive_level", "R") or "R",
        "topic_names": _coerce_topic_names(obj.get("topic_names")),
        "primary_form": _coerce_primary_form(obj.get("primary_form")),
        "figures": _coerce_figures(obj.get("figures")),
    }


class GeminiExtractor:
    """Default Extractor — one native-PDF Gemini call per section A–E.

    Section-chunking keeps the model's attention dense on one section at a time;
    results merge in document order. Provider-agnostic via `LLMClient`.
    """

    def __init__(self, client: LLMClient | None = None):
        self.client = client or make_llm_client()

    def extract(self, pdf_bytes: bytes) -> list[dict]:
        questions: list[dict] = []
        for section in _SECTIONS:
            payload = self.client.extract(
                pdf_bytes, _section_prompt(section), _QUESTION_SCHEMA
            )
            for obj in payload.get("questions", []):
                if isinstance(obj, dict):
                    questions.append(_coerce_question(obj, section))
        return questions


# ---------------------------------------------------------------------------
# Coordinator
# ---------------------------------------------------------------------------


@dataclass
class IngestResult:
    created: int
    skipped_duplicates: int = 0


@dataclass
class _Provenance:
    """Batch-level source provenance derived once per ingested PDF.

    Maps to the contract ``source`` object's batch-wide fields. Per-question
    ``source_page_number`` is a V2 deferral — the extractor does not track page
    offsets yet, so it stays null.
    """

    source_type: str
    source_name: str
    source_file_name: str

    @classmethod
    def from_filename(cls, file_name: str, source_type: str) -> _Provenance:
        file_name = (file_name or "").strip()
        # Derive a human-readable source_name from the filename stem.
        source_name = file_name.rsplit(".", 1)[0].strip() if file_name else ""
        return cls(
            # Default matches Question.source_type's model default: an ingested
            # PDF is a previous-year paper unless the caller says otherwise.
            source_type=(source_type or "").strip() or "previous_year_paper",
            source_name=source_name,
            source_file_name=file_name,
        )


class Ingestor:
    """Pipeline coordinator. Two adapters are injectable: Extractor and DiagramCropper.

    The default constructor wires `GeminiExtractor` + `PyMuPdfCropper`; tests pass
    stubs for either.
    """

    def __init__(
        self,
        extractor: Extractor | None = None,
        cropper: DiagramCropper | None = None,
    ):
        self.extractor = extractor or GeminiExtractor()
        self.cropper = cropper or PyMuPdfCropper()

    def ingest(
        self,
        pdf_bytes: bytes,
        *,
        source_file_name: str = "",
        source_type: str = "",
    ) -> IngestResult:
        """Send a paper PDF to the extractor and persist Question rows.

        ``source_file_name`` (the uploaded filename) and ``source_type`` (one of
        the contract's source kinds, e.g. ``previous_year_paper``) record where a
        batch came from. ``source_name`` is derived from the filename stem.
        """
        raw_questions = self.extractor.extract(pdf_bytes)
        if not raw_questions:
            return IngestResult(created=0)

        # Structural self-assessment — no source-text verification (ADR-0004).
        for q in raw_questions:
            q["parse_quality"] = compute_parse_quality(q, q["qtype"])

        # De-duplication: skip questions already in the bank AND repeats within
        # this PDF.
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

        chapter_by_slug = {c.slug: c for c in Chapter.objects.all()}
        provenance = _Provenance.from_filename(source_file_name, source_type)
        # Crop figure boxes to media assets and rewrite content image references.
        primary_assets = self.cropper.crop(pdf_bytes, raw_questions, fingerprints)
        created = self._persist(
            raw_questions,
            fingerprints,
            primary_assets,
            chapter_by_slug,
            provenance,
        )
        return IngestResult(created=created, skipped_duplicates=skipped)

    @staticmethod
    def _persist(
        tagged: list[dict],
        fingerprints: list[str],
        primary_assets: list[str | None],
        chapter_by_slug: dict[str, Chapter],
        provenance: _Provenance,
    ) -> int:
        rows: list[Question] = []
        for i, q in enumerate(tagged):
            primary_asset = primary_assets[i] if i < len(primary_assets) else None
            primary_form = q.get("primary_form", "none")
            content = q.get("content", {})
            has_diagram = (
                primary_asset is not None
                or primary_form == "diagram_based"
                or _mentions_diagram(q["text"])
                or content_mod.has_item(content, "image", "image_placeholder")
            )

            row = Question(
                chapter=chapter_by_slug.get(q.get("chapter_slug")),
                section=q["section"],
                qtype=q["qtype"],
                marks=q["marks"],
                cognitive_level=q.get("cognitive_level", CognitiveLevel.REMEMBER),
                text=q["text"],
                options=q.get("options", []),
                content=content,
                topic_names=q.get("topic_names", []),
                primary_form=primary_form,
                parse_quality=q.get("parse_quality", "partial"),
                answer=q.get("answer", ""),
                answer_source=q.get("answer_source", ""),
                verified=False,
                has_diagram=has_diagram,
                is_numerical=_detect_numerical(q["text"]),
                source_hash=fingerprints[i],
                source_type=provenance.source_type,
                source_name=provenance.source_name,
                source_file_name=provenance.source_file_name,
                source_page_number=q.get("source_page_number"),
            )
            if primary_asset:
                # File already saved to storage by the DiagramCropper; just point
                # the FileField at it (assetId == storage name) for Admin review.
                row.diagram.name = primary_asset
            rows.append(row)

        Question.objects.bulk_create(rows)
        return len(rows)
