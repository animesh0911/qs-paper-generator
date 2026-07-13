"""Answers scenario: golden drafting freezes the exact judged payload."""

import json

import pytest

from bank.models import Chapter, Question
from evals.scenarios import answers


@pytest.mark.django_db
def test_golden_items_freeze_judge_payload_and_context(tmp_path):
    chapter = Chapter.objects.get(slug="carbon-and-its-compounds")
    question = Question.objects.create(
        section="C",
        qtype="short_answer",
        marks=3,
        text="Why does carbon form covalent bonds?",
        chapter=chapter,
        answer="",
        answer_source="",
    )
    artifact_path = tmp_path / "run.json"
    artifact_path.write_text(
        json.dumps(
            {
                "answers": [
                    {"id": question.pk, "answer": "By sharing electrons."},
                    {"id": 0, "answer": "orphan row without a Question"},
                ]
            }
        ),
        encoding="utf-8",
    )
    record = {"artifacts_path": str(artifact_path), "scenario": "answers"}

    items = answers.golden_items(record, sample=5)

    [(key, payload, context)] = items
    assert key == f"q:{question.pk}"
    assert payload["generated_answer"] == "By sharing electrons."
    assert payload["question"] == "Why does carbon form covalent bonds?"
    assert payload["marks"] == 3
    # No RetrievalChunks are seeded in the test DB, so the frozen context is
    # empty — the no_textbook_context lane the answers rubric handles.
    assert context == ""
