"""Tests for the generate_answers management command.

The command calls generate_text once per unanswered question and stores the
result with answer_source='generated_unverified'. Tests use an injectable stub
so no Gemini key is needed.
"""

from __future__ import annotations

import pytest
from django.core.management import call_command

from bank.management.commands.generate_answers import _build_prompt
from bank.models import AnswerSource, Chapter, Question


def _make_question(**kwargs) -> Question:
    chapter = Chapter.objects.first()
    defaults = {
        "section": "C",
        "qtype": "short_answer",
        "marks": 3,
        "text": "Define Newton's first law.",
        "chapter": chapter,
        "answer": "",
        "answer_source": "",
    }
    defaults.update(kwargs)
    return Question.objects.create(**defaults)


class _StubClient:
    """Returns a canned answer without hitting the network."""

    def __init__(self, answer: str = "Stub answer."):
        self._answer = answer
        self.calls: list[str] = []

    def extract(self, pdf_bytes, prompt, response_schema):
        raise NotImplementedError

    def generate_text(self, prompt, response_schema):
        self.calls.append(prompt)
        return {"answer": self._answer}


@pytest.mark.django_db
def test_generates_answer_and_sets_source(monkeypatch):
    """generate_answers stores the LLM answer with generated_unverified provenance.

    Why this matters: provenance is the gate that separates untrusted
    LLM output from answers the marking scheme can show.
    """
    stub = _StubClient("An object at rest stays at rest.")
    monkeypatch.setattr(
        "bank.management.commands.generate_answers.make_llm_client", lambda: stub
    )

    q = _make_question()
    call_command("generate_answers")

    q.refresh_from_db()
    assert q.answer == "An object at rest stays at rest."
    assert q.answer_source == AnswerSource.GENERATED_UNVERIFIED
    assert len(stub.calls) == 1


@pytest.mark.django_db
def test_skips_already_answered_questions(monkeypatch):
    """Questions with an existing answer are not re-processed."""
    stub = _StubClient()
    monkeypatch.setattr(
        "bank.management.commands.generate_answers.make_llm_client", lambda: stub
    )

    _make_question(
        answer="Already answered.",
        answer_source=AnswerSource.HUMAN,
    )
    call_command("generate_answers")

    assert stub.calls == []


@pytest.mark.django_db
def test_qtype_filter(monkeypatch):
    """--qtype restricts processing to the specified types."""
    stub = _StubClient()
    monkeypatch.setattr(
        "bank.management.commands.generate_answers.make_llm_client", lambda: stub
    )

    mcq = _make_question(qtype="mcq", text="Q MCQ?")
    sa = _make_question(qtype="short_answer", text="Q SA?")

    call_command("generate_answers", qtype=["mcq"])

    mcq.refresh_from_db()
    sa.refresh_from_db()
    assert mcq.answer_source == AnswerSource.GENERATED_UNVERIFIED
    assert sa.answer == ""


@pytest.mark.django_db
def test_limit(monkeypatch):
    """--limit caps the number of questions processed."""
    stub = _StubClient()
    monkeypatch.setattr(
        "bank.management.commands.generate_answers.make_llm_client", lambda: stub
    )

    for i in range(5):
        _make_question(text=f"Question {i}?")

    call_command("generate_answers", limit=2)

    assert len(stub.calls) == 2


@pytest.mark.django_db
def test_failed_question_does_not_abort_batch(monkeypatch):
    """A single LLM failure is reported but the rest of the batch continues."""

    call_count = 0

    class _FailFirst:
        def extract(self, *a, **kw):
            raise NotImplementedError

        def generate_text(self, prompt, schema):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("network error")
            return {"answer": "Good answer."}

    monkeypatch.setattr(
        "bank.management.commands.generate_answers.make_llm_client", _FailFirst
    )

    q1 = _make_question(text="First question?")
    q2 = _make_question(text="Second question?")

    call_command("generate_answers")

    q1.refresh_from_db()
    q2.refresh_from_db()
    assert q1.answer == ""
    assert q2.answer == "Good answer."


@pytest.mark.django_db
def test_dry_run_does_not_write(monkeypatch):
    """--dry-run prints prompts but writes nothing to the database."""
    stub = _StubClient()
    monkeypatch.setattr(
        "bank.management.commands.generate_answers.make_llm_client", lambda: stub
    )

    q = _make_question()
    call_command("generate_answers", dry_run=True)

    q.refresh_from_db()
    assert q.answer == ""
    assert stub.calls == []


@pytest.mark.django_db
def test_build_prompt_tolerates_malformed_options():
    """A malformed option dict must not raise from _build_prompt.

    Why this matters: _build_prompt runs before the per-question try in
    handle(); a KeyError here would abort the whole batch, not one question.
    """
    q = _make_question(
        qtype="mcq",
        options=[{"label": "A"}, {"text": "no label"}, {}],
    )

    prompt = _build_prompt(q)

    assert "A." in prompt
    assert "no label" in prompt
