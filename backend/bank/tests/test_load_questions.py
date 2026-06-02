"""Tests for the load_questions management command.

The command is the no-key ingestion path: committed JSON → _verify → rows. These
tests pin the behaviour issue #55 asks for — verifier-set parse_quality, source
provenance, source_hash dedup on re-run, and one bad file not aborting the
batch. Chapters are provided by migration 0003 under the django_db fixture.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from django.core.management import call_command

from bank.models import Question

# A well-formed two-question paper. Both texts (and the MCQ options) are present
# in source_text in reading order, so _verify leaves their structural quality
# intact: the 4-option MCQ stays clean, the short-answer stays clean.
_SOURCE_TEXT = """\
SECTION A
1. Which gas is released during photosynthesis?
(A) Oxygen (B) Nitrogen (C) Carbon dioxide (D) Hydrogen
SECTION C
2. Define refraction of light.
"""

_MCQ = {
    "section": "A",
    "qtype": "mcq",
    "marks": 1,
    "text": "Which gas is released during photosynthesis?",
    "options": [
        {"label": "A", "text": "Oxygen"},
        {"label": "B", "text": "Nitrogen"},
        {"label": "C", "text": "Carbon dioxide"},
        {"label": "D", "text": "Hydrogen"},
    ],
    "content": {
        "stem": [
            {
                "type": "paragraph",
                "text": "Which gas is released during photosynthesis?",
            }
        ],
        "options": [
            {"label": "A", "content": [{"type": "paragraph", "text": "Oxygen"}]},
            {"label": "B", "content": [{"type": "paragraph", "text": "Nitrogen"}]},
            {
                "label": "C",
                "content": [{"type": "paragraph", "text": "Carbon dioxide"}],
            },
            {"label": "D", "content": [{"type": "paragraph", "text": "Hydrogen"}]},
        ],
    },
    "chapter_slug": "life-processes",
    "cognitive_level": "U",
    "topic_names": ["Photosynthesis"],
    "primary_form": "none",
}

_SA = {
    "section": "C",
    "qtype": "short_answer",
    "marks": 3,
    "text": "Define refraction of light.",
    "options": [],
    "content": {"stem": [{"type": "paragraph", "text": "Define refraction of light."}]},
    "chapter_slug": "light-reflection-and-refraction",
    "cognitive_level": "R",
    "topic_names": ["Refraction"],
    "primary_form": "none",
}


def _write_file(directory: Path, name: str, payload: dict) -> Path:
    path = directory / name
    path.write_text(json.dumps(payload))
    return path


def _payload(
    *questions: dict, source_pdf: str = "science_2024/31_1_1_Science.pdf"
) -> dict:
    return {
        "source_pdf": source_pdf,
        "source_text": _SOURCE_TEXT,
        "questions": [dict(q) for q in questions],
    }


@pytest.mark.django_db
def test_loads_directory_into_rows_with_quality_and_provenance(tmp_path):
    """A fixture file → expected rows, verifier-set parse_quality, source object.

    Why this matters: this is the end-to-end proof the command wires JSON →
    _verify → persist. If a step is dropped, parse_quality or provenance is
    wrong here.
    """
    _write_file(tmp_path, "31_1_1_Science.json", _payload(_MCQ, _SA))

    call_command("load_questions", str(tmp_path))

    assert Question.objects.count() == 2
    mcq = Question.objects.get(qtype="mcq")
    sa = Question.objects.get(qtype="short_answer")

    # Verifier left both clean: faithful, in order, full structure.
    assert mcq.parse_quality == "clean"
    assert sa.parse_quality == "clean"

    # Reviewed data lands unverified — verified emerges from Paper.approve (ADR-0002).
    assert mcq.verified is False
    # Hand tags + structured content survive the load.
    assert mcq.chapter.slug == "life-processes"
    assert mcq.cognitive_level == "U"
    assert mcq.topic_names == ["Photosynthesis"]
    assert mcq.content["options"][0]["label"] == "A"

    # Provenance derived from the recorded source PDF name via _parse_source_filename.
    assert mcq.source_type == "previous_year_paper"
    assert mcq.source_name == "31-1-1 Science 2024"
    assert mcq.source_file_name == "31_1_1_Science.pdf"


@pytest.mark.django_db
def test_verifier_marks_unfaithful_text_broken(tmp_path):
    """A question whose text is absent from source_text is forced to broken.

    Why this matters: proves _verify actually runs in the loader (not a no-op).
    If the source_text guardrail were skipped, this row would persist as clean.
    """
    fabricated = {**_SA, "text": "State Newton's third law of motion."}
    _write_file(tmp_path, "paper.json", _payload(_MCQ, fabricated))

    call_command("load_questions", str(tmp_path))

    bad = Question.objects.get(text="State Newton's third law of motion.")
    assert bad.parse_quality == "broken"


@pytest.mark.django_db
def test_rerun_does_not_duplicate(tmp_path):
    """source_hash dedup makes the command idempotent across runs."""
    _write_file(tmp_path, "paper.json", _payload(_MCQ, _SA))

    call_command("load_questions", str(tmp_path))
    call_command("load_questions", str(tmp_path))

    assert Question.objects.count() == 2


@pytest.mark.django_db
def test_malformed_file_skipped_not_fatal(tmp_path):
    """A malformed file is reported and skipped; valid files still load."""
    (tmp_path / "broken.json").write_text("{ this is not valid json")
    _write_file(tmp_path, "good.json", _payload(_MCQ, _SA))

    call_command("load_questions", str(tmp_path))

    # The valid file's rows landed despite the broken sibling.
    assert Question.objects.count() == 2
