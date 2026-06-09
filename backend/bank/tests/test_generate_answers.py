"""Tests for the generate_answers management command.

The command builds its chat model through the model seam and asks for answers in
batches, storing each with answer_source='generated_unverified'. Tests inject a
fake model factory onto a Command instance (no module patching, Rules 9/11) so
the GenericFakeChatModel returns canned batch JSON without a key or network.
"""

from __future__ import annotations

import json

import pytest
from django.core.management import CommandError, call_command
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from bank.management.commands.generate_answers import Command, _render_question
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


def _batch_msg(pairs) -> AIMessage:
    """A model reply answering the given (question_id, answer) pairs."""
    payload = {"answers": [{"id": qid, "answer": ans} for qid, ans in pairs]}
    return AIMessage(content=json.dumps(payload))


class _FakeFactory:
    """A make_model stand-in: returns one GenericFakeChatModel that yields the
    supplied replies (one per batch call) and records how many models it built."""

    def __init__(self, *replies: AIMessage):
        self._replies = list(replies)
        self.build_count = 0

    def __call__(self, purpose):
        self.build_count += 1
        return GenericFakeChatModel(messages=iter(self._replies))


def _run(factory: _FakeFactory | None, **options):
    cmd = Command()
    if factory is not None:
        cmd.make_model = factory
    call_command(cmd, **options)


@pytest.mark.django_db
def test_generates_answer_and_sets_source():
    """generate_answers stores the LLM answer with generated_unverified provenance.

    Why this matters: provenance is the gate that separates untrusted LLM output
    from answers the marking scheme can show.
    """
    q = _make_question()
    factory = _FakeFactory(_batch_msg([(q.pk, "An object at rest stays at rest.")]))

    _run(factory)

    q.refresh_from_db()
    assert q.answer == "An object at rest stays at rest."
    assert q.answer_source == AnswerSource.GENERATED_UNVERIFIED


@pytest.mark.django_db
def test_skips_already_answered_questions():
    """Questions with an existing answer are not processed — and with nothing to
    do, no model is even built (no needless cost)."""
    _make_question(answer="Already answered.", answer_source=AnswerSource.HUMAN)
    factory = _FakeFactory(_batch_msg([]))

    _run(factory)

    assert factory.build_count == 0


@pytest.mark.django_db
def test_qtype_filter():
    """--qtype restricts processing to the specified types."""
    mcq = _make_question(qtype="mcq", text="Q MCQ?")
    sa = _make_question(qtype="short_answer", text="Q SA?")
    factory = _FakeFactory(_batch_msg([(mcq.pk, "A. Correct option.")]))

    _run(factory, qtype=["mcq"])

    mcq.refresh_from_db()
    sa.refresh_from_db()
    assert mcq.answer_source == AnswerSource.GENERATED_UNVERIFIED
    assert sa.answer == ""


@pytest.mark.django_db
def test_limit_caps_questions_processed():
    """--limit caps how many questions enter the run; the rest are untouched."""
    questions = [_make_question(text=f"Question {i}?") for i in range(5)]
    # Reply offers answers for every id; only those in the (limited) batch apply.
    factory = _FakeFactory(_batch_msg([(q.pk, "ans") for q in questions]))

    _run(factory, limit=2)

    answered = [q for q in questions if Question.objects.get(pk=q.pk).answer]
    assert len(answered) == 2


@pytest.mark.django_db
def test_batching_splits_into_multiple_calls():
    """With batch_size < count, the run makes one call per batch and answers all.

    Why this matters: batching is the cost lever — if the command silently sent
    one call per question (or dropped the trailing partial batch), it would
    defeat the reason for batching.
    """
    q1, q2, q3 = (_make_question(text=f"Q{i}?") for i in range(3))
    factory = _FakeFactory(
        _batch_msg([(q1.pk, "a1"), (q2.pk, "a2")]),  # batch 1 (size 2)
        _batch_msg([(q3.pk, "a3")]),  # batch 2 (trailing 1)
    )

    _run(factory, batch_size=2)

    for q, expected in [(q1, "a1"), (q2, "a2"), (q3, "a3")]:
        q.refresh_from_db()
        assert q.answer == expected


@pytest.mark.django_db
def test_failed_batch_does_not_abort_run():
    """A single bad batch is reported but later batches still run.

    Why this matters: with batching the failure unit is the batch, not the
    question; one unparseable reply must not cost the whole run.
    """
    q1 = _make_question(text="First question?")
    q2 = _make_question(text="Second question?")
    factory = _FakeFactory(
        AIMessage(content="not valid json"),  # batch 1 fails to parse
        _batch_msg([(q2.pk, "Good answer.")]),  # batch 2 succeeds
    )

    _run(factory, batch_size=1)

    q1.refresh_from_db()
    q2.refresh_from_db()
    assert q1.answer == ""
    assert q2.answer == "Good answer."


@pytest.mark.django_db
def test_missing_answer_in_batch_is_skipped_not_crashed():
    """If the model omits a question from its reply, that question is left
    unanswered rather than crashing the batch or writing an empty answer."""
    q1 = _make_question(text="Answered question?")
    q2 = _make_question(text="Omitted question?")
    factory = _FakeFactory(_batch_msg([(q1.pk, "Here.")]))  # q2 absent

    _run(factory, batch_size=10)

    q1.refresh_from_db()
    q2.refresh_from_db()
    assert q1.answer == "Here."
    assert q2.answer == ""


@pytest.mark.django_db
def test_dry_run_does_not_write_or_call_model():
    """--dry-run prints prompts but writes nothing and builds no model."""
    q = _make_question()
    factory = _FakeFactory(_batch_msg([(q.pk, "x")]))

    _run(factory, dry_run=True)

    q.refresh_from_db()
    assert q.answer == ""
    assert factory.build_count == 0


@pytest.mark.django_db
def test_batch_size_must_be_positive():
    _make_question()
    with pytest.raises(CommandError, match="--batch-size must be at least 1"):
        _run(_FakeFactory(), batch_size=0)


@pytest.mark.django_db
def test_render_question_tolerates_malformed_options():
    """A malformed option dict must not raise from _render_question.

    Why this matters: rendering runs before the per-batch try in handle(); a
    KeyError here would abort the whole batch, not skip one question.
    """
    q = _make_question(
        qtype="mcq",
        options=[{"label": "A"}, {"text": "no label"}, {}],
    )

    block = _render_question(q)

    assert "A." in block
    assert "no label" in block
