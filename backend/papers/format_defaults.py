"""Backend-owned visible defaults for PaperDocumentV1 formats.

``PaperFormat`` rows own the renderer selection (page/layout) plus the editable
visible text blocks a teacher sees in the paper. The helpers here render the
stored block templates with paper-specific values and merge missing defaults
into older saved documents without overwriting teacher edits.
"""

from __future__ import annotations

from copy import deepcopy
from string import Formatter
from typing import Any

CBSE_COMPACT_FORMAT_ID = "cbse_science_class_10_board_compact_2026_v1"

CBSE_COMPACT_CHROME_BLOCKS: list[dict[str, Any]] = [
    {
        "id": "series",
        "role": "series",
        "text": "LMNK2",
        "can": {"editText": True, "delete": True, "reorder": False},
    },
    {
        "id": "set",
        "role": "set",
        "text": "SET ~ 1",
        "can": {"editText": True, "delete": True, "reorder": False},
    },
    {
        "id": "paper_code",
        "role": "paper_code",
        "text": "31/2/1",
        "can": {"editText": True, "delete": True, "reorder": False},
    },
    {
        "id": "subject_label",
        "role": "subject_label",
        "text": "विज्ञान",
        "can": {"editText": True, "delete": True, "reorder": False},
    },
    {
        "id": "roll_number",
        "role": "roll_number",
        "text": "",
        "can": {"editText": True, "delete": True, "reorder": False},
    },
    {
        "id": "time_allowed",
        "role": "paper_meta_left",
        "text": "Time allowed : {duration}",
        "can": {"editText": True, "delete": True, "reorder": False},
    },
    {
        "id": "maximum_marks",
        "role": "paper_meta_right",
        "text": "Maximum Marks : {totalMarks}",
        "can": {"editText": True, "delete": True, "reorder": False},
    },
    {
        "id": "footer_left",
        "role": "footer_left",
        "text": "31/2/1",
        "can": {"editText": True, "delete": True, "reorder": False},
    },
    {
        "id": "footer_right",
        "role": "footer_right",
        "text": "P.T.O.",
        "can": {"editText": True, "delete": True, "reorder": False},
    },
]

CBSE_COMPACT_INSTRUCTION_BLOCKS: list[dict[str, Any]] = [
    {
        "id": "note_heading",
        "role": "note_heading",
        "text": "NOTE",
        "can": {"editText": True, "delete": False, "reorder": False},
    },
    {
        "id": "note_printed_pages",
        "role": "note",
        "text": "Please check that this question paper contains the correct "
        "number of printed pages.",
        "can": {"editText": True, "delete": False, "reorder": False},
    },
    {
        "id": "note_question_count",
        "role": "note",
        "text": "Please check that this question paper contains "
        "{questionCount} questions.",
        "can": {"editText": True, "delete": False, "reorder": False},
    },
    {
        "id": "note_serial_number",
        "role": "note",
        "text": "Please write down the Serial Number of the question in the "
        "answer-book at the given place before attempting it.",
        "can": {"editText": True, "delete": False, "reorder": False},
    },
    {
        "id": "note_reading_time",
        "role": "note",
        "text": "15 minute time has been allotted to read this question paper. "
        "The question paper will be distributed at 10.15 a.m. From 10.15 a.m. "
        "to 10.30 a.m., the candidates will read the question paper only and "
        "will not write any answer on the answer-book during this period.",
        "can": {"editText": True, "delete": False, "reorder": False},
    },
    {
        "id": "general_instructions_heading",
        "role": "general_instructions_heading",
        "text": "General Instructions",
        "can": {"editText": True, "delete": False, "reorder": False},
    },
    {
        "id": "general_instruction_count",
        "role": "general_instruction",
        "text": "This question paper contains {questionCount} questions. "
        "All questions are compulsory.",
        "can": {"editText": True, "delete": False, "reorder": False},
    },
    {
        "id": "general_instruction_types",
        "role": "general_instruction",
        "text": "The question paper has MCQs, very short answer, short answer, "
        "long answer and case-based questions. Marks are given against each "
        "question.",
        "can": {"editText": True, "delete": False, "reorder": False},
    },
    {
        "id": "general_instruction_choice",
        "role": "general_instruction",
        "text": "There is no overall choice in the question paper. However, an "
        "internal choice has been provided in some questions. Only one of the "
        "choices in such questions must be attempted.",
        "can": {"editText": True, "delete": False, "reorder": False},
    },
]


def render_text_blocks(
    blocks: list[dict[str, Any]],
    *,
    total_marks: int,
    duration_minutes: int,
    question_count: int,
) -> list[dict[str, Any]]:
    context = {
        "totalMarks": total_marks,
        "duration": duration_label(duration_minutes),
        "durationMinutes": duration_minutes,
        "questionCount": question_count,
    }
    rendered = deepcopy(blocks)
    for block in rendered:
        text = block.get("text")
        if isinstance(text, str):
            block["text"] = _safe_format(text, context)
    return rendered


def merge_missing_text_blocks(
    existing: list[dict[str, Any]] | None,
    defaults: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Append missing format blocks without replacing saved teacher edits."""
    result = list(existing or [])
    seen_ids = {block.get("id") for block in result if isinstance(block, dict)}
    seen_roles = {block.get("role") for block in result if isinstance(block, dict)}
    for block in defaults:
        block_id = block.get("id")
        role = block.get("role")
        if block_id in seen_ids or role in seen_roles:
            continue
        result.append(deepcopy(block))
    return result


def duration_label(duration_minutes: int) -> str:
    if duration_minutes % 60 == 0:
        hours = duration_minutes // 60
        return f"{hours} hour{'s' if hours != 1 else ''}"
    return f"{duration_minutes} minutes"


def _safe_format(template: str, context: dict[str, Any]) -> str:
    allowed = {name for _, name, _, _ in Formatter().parse(template) if name}
    if not allowed:
        return template
    return template.format(**{key: context.get(key, "") for key in allowed})
