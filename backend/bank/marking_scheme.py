"""Marking scheme ingestion: parse an official CBSE marking-scheme PDF and
match answers back to existing unverified Question rows.

Parse strategy: look for lines of the form
    "1. <answer text>"   or   "Q1   <answer text>"   or   "Ans. <answer>"
and collect them into a {question_number: answer_text} mapping.

Match strategy: for each answer, find the Question row whose `source_hash`
fingerprint or sequential order matches the question number in the paper.
In practice CBSE marking schemes list answers in the same numbered order as
the question paper, so we match by question number within each section.
"""
from __future__ import annotations

import io
import re

import pdfplumber

from .models import Question

_ANS_LINE_RE = re.compile(
    r"""
    ^\s*
    (?:Q\.?\s*)?          # optional "Q" prefix
    (\d{1,2})             # question number
    [.)\s]+               # separator
    (.+)                  # answer text (rest of line)
    """,
    re.VERBOSE,
)

_ANS_HEADER_RE = re.compile(r"\bAns(?:wer)?\.?\s*[:—-]?\s*(.+)", re.IGNORECASE)


def parse_marking_scheme(pdf_bytes: bytes) -> dict[int, str]:
    """Extract {question_number: answer_text} from a marking-scheme PDF."""
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    answers: dict[int, str] = {}
    current_qnum: int | None = None
    current_lines: list[str] = []

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        # "Ans." continuation line — append to current question's answer.
        m_ans = _ANS_HEADER_RE.match(line)
        if m_ans and current_qnum is not None:
            current_lines.append(m_ans.group(1).strip())
            continue

        m_num = _ANS_LINE_RE.match(line)
        if m_num:
            # Flush previous.
            if current_qnum is not None:
                answers[current_qnum] = " ".join(current_lines).strip()
            current_qnum = int(m_num.group(1))
            current_lines = [m_num.group(2).strip()]
        elif current_qnum is not None:
            # Continuation of multi-line answer.
            current_lines.append(line)

    if current_qnum is not None:
        answers[current_qnum] = " ".join(current_lines).strip()

    return answers


def apply_marking_scheme(pdf_bytes: bytes) -> int:
    """Parse a marking-scheme PDF and update Question.answer for matched rows.

    Matches unverified questions in insertion order (the order they were
    ingested mirrors the paper's question numbering).

    Returns count of updated rows.
    """
    scheme = parse_marking_scheme(pdf_bytes)
    if not scheme:
        return 0

    # Fetch unverified questions ordered by id (insertion order = paper order).
    questions = list(Question.objects.filter(verified=False).order_by("id"))
    updated = 0

    for q_num, answer_text in scheme.items():
        # q_num is 1-indexed.
        idx = q_num - 1
        if 0 <= idx < len(questions) and answer_text:
            q = questions[idx]
            q.answer = answer_text
            q.save(update_fields=["answer"])
            updated += 1

    return updated
