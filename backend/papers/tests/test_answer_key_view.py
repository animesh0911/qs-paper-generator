"""Gate tests for PaperAnswerKeyPdfView._answers_by_id.

The marking scheme must never reveal an LLM answer a human has not approved
(issue #87 AC: generated answers gated behind a human verify step). The gate
lives in the view's answer-map builder, not the renderer, so it is tested here
directly against questions of each answer_source.
"""

from __future__ import annotations

import pytest

from bank.models import AnswerSource
from conftest import QuestionFactory
from papers.models import Paper
from papers.views import PaperAnswerKeyPdfView


def _paper_with(user, *questions) -> Paper:
    """A Paper whose document selects every given question, one slot each."""
    slots = [{"selectedQuestionId": f"q_{q.pk}"} for q in questions]
    document = {"paper": {"sections": [{"slots": slots}]}}
    return Paper.objects.create(created_by=user, document=document)


@pytest.mark.django_db
def test_generated_unverified_answer_is_suppressed(user):
    """An unverified generated answer must not reach the marking scheme.

    Why this matters: this is the trust boundary — blind LLM output in a
    marking scheme is the failure mode #87 exists to prevent.
    """
    unverified = QuestionFactory(
        answer="Bluffed answer", answer_source=AnswerSource.GENERATED_UNVERIFIED
    )
    paper = _paper_with(user, unverified)

    answers = PaperAnswerKeyPdfView()._answers_by_id(paper)

    assert f"q_{unverified.pk}" not in answers


@pytest.mark.django_db
def test_approved_and_human_answers_pass_through(user):
    """Human-entered and human-approved generated answers are revealed."""
    human = QuestionFactory(answer="Real answer", answer_source=AnswerSource.HUMAN)
    approved = QuestionFactory(
        answer="Checked answer", answer_source=AnswerSource.GENERATED_VERIFIED
    )
    extracted = QuestionFactory(answer="From key", answer_source=AnswerSource.EXTRACTED)
    paper = _paper_with(user, human, approved, extracted)

    answers = PaperAnswerKeyPdfView()._answers_by_id(paper)

    assert answers[f"q_{human.pk}"] == "Real answer"
    assert answers[f"q_{approved.pk}"] == "Checked answer"
    assert answers[f"q_{extracted.pk}"] == "From key"
