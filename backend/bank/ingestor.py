"""Ingestion A: parse a CBSE past-paper PDF and auto-tag questions via an LLM.

`Ingestor` is the coordinator. It runs the pipeline and persists Question rows
(verified=False). Two seams are injected as adapters:

* `Parser` — turns PDF bytes into plain text. Default: `PdfplumberParser`.
* `Tagger` — assigns chapter_slug + cognitive_level to each raw question.
             Default: `LLMTagger` (uses any provider via `bank.llm.LLMClient`).

`strip_hindi` and `segment_questions` are pure helpers between the two seams;
they're not configurable so they remain module-level functions.

Tests construct ad-hoc Parser/Tagger stubs and pass them to Ingestor —
no module-level patching required.
"""
from __future__ import annotations

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


class Tagger(Protocol):
    def tag(
        self, raw_questions: list[dict], chapters: list[Chapter]
    ) -> list[dict]: ...


class PdfplumberParser:
    """Default Parser — extracts text from each PDF page via pdfplumber."""

    def parse(self, pdf_bytes: bytes) -> str:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)


class LLMTagger:
    """Default Tagger — batches questions to an LLM for chapter/level tagging.

    Provider-agnostic: takes any `LLMClient`. Defaults to the one
    `make_llm_client()` returns (driven by `LLM_PROVIDER` env var).
    """

    def __init__(self, client: LLMClient | None = None):
        self.client = client or make_llm_client()

    def tag(
        self, raw_questions: list[dict], chapters: list[Chapter]
    ) -> list[dict]:
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
            # Strip markdown fences if the model wraps output
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


# ---------------------------------------------------------------------------
# Coordinator
# ---------------------------------------------------------------------------


@dataclass
class IngestResult:
    created: int


class Ingestor:
    """Pipeline coordinator. Parser + Tagger are injectable adapters.

    The default constructor wires the production adapters
    (PdfplumberParser, LLMTagger); tests pass stubs.
    """

    def __init__(
        self,
        parser: Parser | None = None,
        tagger: Tagger | None = None,
    ):
        self.parser = parser or PdfplumberParser()
        self.tagger = tagger or LLMTagger()

    def ingest(self, pdf_bytes: bytes) -> IngestResult:
        raw_text = self.parser.parse(pdf_bytes)
        clean_text = strip_hindi(raw_text)
        raw_questions = segment_questions(clean_text)
        if not raw_questions:
            return IngestResult(created=0)

        chapters = list(Chapter.objects.all())
        tagged = self.tagger.tag(raw_questions, chapters)
        chapter_by_slug = {c.slug: c for c in chapters}
        created = self._persist(tagged, chapter_by_slug)
        return IngestResult(created=created)

    @staticmethod
    def _persist(tagged: list[dict], chapter_by_slug: dict[str, Chapter]) -> int:
        rows = [
            Question(
                chapter=chapter_by_slug.get(q.get("chapter_slug")),
                section=q["section"],
                qtype=q["qtype"],
                marks=q["marks"],
                cognitive_level=q.get("cognitive_level", CognitiveLevel.REMEMBER),
                text=q["text"],
                options=q.get("options", []),
                answer="",
                verified=False,
            )
            for q in tagged
        ]
        Question.objects.bulk_create(rows)
        return len(rows)
