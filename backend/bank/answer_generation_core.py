"""Pure answer-generation core shared by production, commands, and evals.

This module deliberately has no ORM or persistence dependency. Callers adapt a
stored ``Question`` or a JSON extraction artifact into :class:`AnswerQuestion`,
then run the exact same prompt/parser/model path. This keeps model comparisons
honest and permits paid evaluations without database writes.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

_QTYPE_HINT = {
    "mcq": "Write the correct option label and option text.",
    "assertion_reason": (
        "State whether assertion/reason are true and whether the reason "
        "correctly explains the assertion."
    ),
    "very_short_answer": "Write a concise answer in 1-3 sentences (max 50 words).",
    "short_answer": "Write a model answer in 3-5 sentences (max 80 words).",
    "long_answer": "Write a structured model answer with key points (max 200 words).",
    "case_based": "Address each sub-part of the case study in order.",
    "internal_choice": "Provide a model answer for one of the choices only.",
}

# Stored image URLs/base64 are not useful to a text-only answer model and can be
# very large. Descriptions, captions, table rows, equations, and LaTeX survive.
_MEDIA_KEYS = {
    "assetId",
    "asset_id",
    "base64",
    "data",
    "dataUrl",
    "data_url",
    "path",
    "src",
    "url",
}


@dataclass(frozen=True)
class AnswerQuestion:
    """Provider-neutral input to answer generation."""

    id: int
    qtype: str
    marks: int
    chapter: str
    text: str
    options: tuple[dict[str, Any], ...] = ()
    content: dict[str, Any] | None = None

    @classmethod
    def from_model(cls, question: Any) -> AnswerQuestion:
        chapter = getattr(question, "chapter", None)
        chapter_name = getattr(chapter, "name", None) or "unknown chapter"
        return cls(
            id=int(question.pk),
            qtype=str(question.qtype),
            marks=int(question.marks),
            chapter=str(chapter_name),
            text=str(question.text or ""),
            options=tuple(
                item for item in (question.options or []) if isinstance(item, dict)
            ),
            content=question.content if isinstance(question.content, dict) else {},
        )

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> AnswerQuestion:
        """Adapt a saved extraction artifact without touching Django/DB."""
        chapter = (
            value.get("chapter")
            or value.get("chapter_name")
            or value.get("chapter_slug")
            or "unknown chapter"
        )
        raw_id = value.get("id", value.get("question_id"))
        if raw_id is None:
            raise ValueError("Answer question requires id or question_id")
        return cls(
            id=int(raw_id),
            qtype=str(value.get("qtype") or "short_answer"),
            marks=int(value.get("marks") or 3),
            chapter=str(chapter),
            text=str(value.get("text") or value.get("rawText") or ""),
            options=tuple(
                item for item in (value.get("options") or []) if isinstance(item, dict)
            ),
            content=(
                dict(value.get("content") or {})
                if isinstance(value.get("content"), Mapping)
                else {}
            ),
        )


@dataclass(frozen=True)
class AnswerBatchResult:
    """Accepted answers plus semantic diagnostics for one paid model call."""

    accepted: tuple[dict[str, Any], ...] = ()
    missing_ids: tuple[int, ...] = ()
    duplicate_ids: tuple[int, ...] = ()
    unexpected_ids: tuple[int, ...] = ()
    blank_ids: tuple[int, ...] = ()


class GeneratedAnswer(BaseModel):
    id: int = Field(description="Question id being answered.")
    answer: str = Field(description="Model answer text only.")


class BatchAnswers(BaseModel):
    answers: list[GeneratedAnswer]


def _is_empty(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def _sanitise_content(value: Any) -> Any:
    if isinstance(value, Mapping):
        result = {}
        for key, item in value.items():
            if key in _MEDIA_KEYS:
                continue
            cleaned = _sanitise_content(item)
            if not _is_empty(cleaned):
                result[str(key)] = cleaned
        return result
    if isinstance(value, (list, tuple)):
        # Preserve list positions: empty table cells and option slots can carry
        # meaning even though empty mapping fields do not.
        return [_sanitise_content(item) for item in value]
    return value


def _plain_paragraph_stem(content: Mapping[str, Any]) -> str | None:
    stem = content.get("stem")
    if not isinstance(stem, list) or not stem:
        return None
    if not all(
        isinstance(item, Mapping) and item.get("type") in (None, "paragraph")
        for item in stem
    ):
        return None
    return " ".join(str(item.get("text") or "").strip() for item in stem).strip()


def _has_structured_detail(
    content: Mapping[str, Any] | None, flat_text: str = ""
) -> bool:
    """Whether content carries information beyond the canonical flat text."""
    if not content:
        return False
    # Preserve every non-empty region, including future schema additions. The
    # sanitizer below removes binary/media locations while keeping captions and
    # other answer-relevant metadata.
    if any(value for key, value in content.items() if key != "stem"):
        return True
    stem = content.get("stem")
    if not isinstance(stem, list):
        return False
    paragraph_text = " ".join(
        str(item.get("text") or "").strip()
        for item in stem
        if isinstance(item, Mapping)
    ).strip()
    if len(stem) > 1 or (
        paragraph_text
        and " ".join(paragraph_text.split()) != " ".join(flat_text.split())
    ):
        return True
    return any(
        isinstance(item, Mapping)
        and (
            item.get("type") not in (None, "paragraph")
            or bool(item.get("latex"))
            or bool(item.get("rows"))
        )
        for item in stem
    )


def render_answer_question(question: AnswerQuestion) -> str:
    hint = _QTYPE_HINT.get(question.qtype, "Write a concise model answer.")
    marks = f"{question.marks} mark{'s' if question.marks != 1 else ''}"
    heading = (
        f"[id={question.id}] Type: {question.qtype} ({marks}); "
        f"Chapter: {question.chapter}"
    )
    lines = [heading, f"  Question: {question.text}"]
    if question.options:
        lines.append("  Options:")
        lines.extend(
            f"    {option.get('label', '?')}. {option.get('text', '')}"
            for option in question.options
        )
    if _has_structured_detail(question.content, question.text):
        cleaned_content = _sanitise_content(question.content)
        # ``Question.text`` already carries an ordinary paragraph-only stem.
        # Remove that exact duplicate while retaining richer stems containing
        # equations/tables/images and every other structured region.
        stem_text = _plain_paragraph_stem(cleaned_content)
        if stem_text and " ".join(stem_text.split()) == " ".join(question.text.split()):
            cleaned_content.pop("stem", None)
        structured = json.dumps(
            cleaned_content,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        lines.extend(
            [
                "  Structured content (passages, subparts, equations and tables):",
                f"    {structured}",
            ]
        )
    lines.append(f"  Instruction: {hint}")
    return "\n".join(lines)


def build_answer_prompt(
    questions: Sequence[AnswerQuestion], format_instructions: str
) -> str:
    blocks = "\n\n".join(render_answer_question(question) for question in questions)
    return (
        "Generate CBSE Class 10 Science model answers for the questions below. "
        "Return one answer for each id. Return persistable answer text only: no "
        "preamble and no restatement of the question.\n"
        "Match answer depth to the marks, roughly one key point per mark, in "
        "CBSE marking-scheme style. For numerical questions, show the formula, "
        "substitution, final value and SI unit, and verify the arithmetic and sign. "
        "When balancing a supplied equation, retain every species shown and balance "
        "that exact equation. Use both the Question text and all Structured content "
        "supplied. When Structured content contains choices, answer exactly one "
        "alternative: use the first complete answerable alternative. Do not include "
        "the unselected alternative or the word OR. If a question depends on an "
        "unavailable visual, answer only what the supplied text supports and note "
        "the dependency briefly; never invent labels or values.\n"
        "Return one single valid JSON object matching the output schema. Check that "
        "all brackets and braces are balanced. Do not wrap the JSON in Markdown "
        "fences and do not add text before or after it.\n\n"
        f"{blocks}\n\n{format_instructions}"
    )


class AnswerGenerator:
    """One production prompt/parser around an injected chat model."""

    def __init__(self, chat_model: BaseChatModel):
        self.parser = PydanticOutputParser(pydantic_object=BatchAnswers)
        self.chain = chat_model | self.parser

    def generate(self, questions: Sequence[AnswerQuestion]) -> AnswerBatchResult:
        if not questions:
            return AnswerBatchResult()
        result = self.chain.invoke(
            build_answer_prompt(questions, self.parser.get_format_instructions())
        )
        expected = {question.id for question in questions}
        accepted: list[dict[str, Any]] = []
        accepted_ids: set[int] = set()
        seen: set[int] = set()
        duplicate_ids: list[int] = []
        unexpected_ids: list[int] = []
        blank_ids: list[int] = []
        for item in result.answers:
            if item.id not in expected:
                if item.id not in unexpected_ids:
                    unexpected_ids.append(item.id)
                continue
            if item.id in seen:
                if item.id not in duplicate_ids:
                    duplicate_ids.append(item.id)
                continue
            seen.add(item.id)
            answer = item.answer.strip()
            if not answer:
                blank_ids.append(item.id)
                continue
            accepted_ids.add(item.id)
            accepted.append({"id": item.id, "answer": answer})
        return AnswerBatchResult(
            accepted=tuple(accepted),
            missing_ids=tuple(
                question.id for question in questions if question.id not in accepted_ids
            ),
            duplicate_ids=tuple(duplicate_ids),
            unexpected_ids=tuple(unexpected_ids),
            blank_ids=tuple(blank_ids),
        )

    def generate_mappings(
        self, questions: Iterable[Mapping[str, Any]]
    ) -> AnswerBatchResult:
        """No-DB entry point for saved extraction artifacts and external evals."""
        return self.generate([AnswerQuestion.from_mapping(item) for item in questions])
