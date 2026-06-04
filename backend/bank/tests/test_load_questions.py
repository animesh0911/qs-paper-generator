"""Tests for the load_questions management command.

The command is the no-key ingestion path: committed JSON → structural
parse_quality → rows. These tests pin the behaviour — coordinator-set
parse_quality, source provenance, source_hash dedup on re-run, and one bad file
not aborting the batch. Chapters are provided by migration 0003 under the
django_db fixture.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from django.core.management import call_command

from bank.models import Question

# A well-formed two-question paper. The 4-option MCQ and the non-empty short
# answer both self-assess as clean via _compute_parse_quality. A legacy
# source_text field is kept here only to prove the loader ignores it.
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
    """A fixture file → expected rows, structural parse_quality, source object.

    Why this matters: this is the end-to-end proof the command wires JSON →
    parse_quality → persist. If a step is dropped, parse_quality or provenance is
    wrong here.
    """
    _write_file(tmp_path, "31_1_1_Science.json", _payload(_MCQ, _SA))

    call_command("load_questions", str(tmp_path))

    assert Question.objects.count() == 2
    mcq = Question.objects.get(qtype="mcq")
    sa = Question.objects.get(qtype="short_answer")

    # parse_quality set structurally: 4-option mcq + non-empty short answer.
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
def test_parse_quality_is_structural_not_source_based(tmp_path):
    """parse_quality is a structural self-assessment now (ADR-0004), not a
    fidelity check against source text.

    Why this matters: proves the loader sets parse_quality from structure — an
    mcq with no options is broken regardless of any text, while a well-formed
    short answer is clean. There is no source-text verification pass anymore.
    """
    broken_mcq = {**_MCQ, "options": [], "content": {}}
    _write_file(tmp_path, "paper.json", _payload(broken_mcq, _SA))

    call_command("load_questions", str(tmp_path))

    assert Question.objects.get(qtype="mcq").parse_quality == "broken"
    assert Question.objects.get(qtype="short_answer").parse_quality == "clean"


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


@pytest.mark.django_db
def test_answer_and_answer_source_survive_load(tmp_path):
    """answer + answer_source in the JSON are stored verbatim on the row.

    Why this matters: committed JSON produced by the extraction pipeline carries
    pre-generated answers; load_questions must preserve them so the marking
    scheme is populated without a separate generate_answers run.
    """
    mcq_with_answer = {
        **_MCQ,
        "answer": "A",
        "answer_source": "human",
    }
    _write_file(tmp_path, "paper.json", _payload(mcq_with_answer))

    call_command("load_questions", str(tmp_path))

    q = Question.objects.get(qtype="mcq")
    assert q.answer == "A"
    assert q.answer_source == "human"


@pytest.mark.django_db
def test_missing_answer_fields_default_to_blank(tmp_path):
    """Questions without answer/answer_source in JSON get empty strings (no crash)."""
    _write_file(tmp_path, "paper.json", _payload(_MCQ))

    call_command("load_questions", str(tmp_path))

    q = Question.objects.get(qtype="mcq")
    assert q.answer == ""
    assert q.answer_source == ""


@pytest.mark.django_db
def test_rehydrates_committed_assets_into_storage(tmp_path, settings):
    """Committed crop PNGs in <dir>/assets/ are copied into default_storage.

    Why this matters: the committed JSON references diagrams by storage name; if
    the loader didn't re-hydrate the asset, that reference would 404 on a fresh
    checkout and the diagram would silently vanish from the rendered paper."""
    from django.core.files.storage import default_storage

    settings.MEDIA_ROOT = str(tmp_path / "media")
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "abcd1234-0.png").write_bytes(b"\x89PNG\r\n\x1a\nfake")
    _write_file(tmp_path, "paper.json", _payload(_MCQ))

    call_command("load_questions", str(tmp_path))

    assert default_storage.exists("diagrams/abcd1234-0.png")


@pytest.mark.django_db
def test_rehydration_is_idempotent(tmp_path, settings):
    """Re-running the loader does not duplicate an already-present asset."""
    from django.core.files.storage import default_storage

    settings.MEDIA_ROOT = str(tmp_path / "media")
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "abcd1234-0.png").write_bytes(b"\x89PNG\r\n\x1a\nfake")
    _write_file(tmp_path, "paper.json", _payload(_MCQ))

    call_command("load_questions", str(tmp_path))
    call_command("load_questions", str(tmp_path))

    # Exact storage name preserved (no "_<suffix>" collision copies).
    stored = default_storage.listdir("diagrams")[1]
    assert stored == ["abcd1234-0.png"]
