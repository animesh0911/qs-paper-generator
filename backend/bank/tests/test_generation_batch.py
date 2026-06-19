"""Tests for persisted bulk Question-generation batches.

The lifecycle is deliberately database-backed: HTTP creates and polls
``GenerationBatch`` rows, while ``drain_generation_batches`` is the only place
that asks the generation seam for candidates. All tests use fakes, never a paid
model call.
"""

from __future__ import annotations

from datetime import timedelta

from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import School
from bank.management.commands import drain_generation_batches as drain_mod
from bank.models import (
    AnswerSource,
    GeneratedQuestionCandidate,
    GeneratedQuestionCandidateStatus,
    GenerationBatch,
    GenerationBatchStatus,
    Question,
    SourceType,
)


def _payload(**overrides):
    payload = {
        "chapter_slug": "life-processes",
        "qtype": "mcq",
        "marks": 1,
        "cognitive_level": "R",
        "raw_text": "Which process releases energy from glucose?",
        "content": {
            "stem": [{"type": "paragraph", "text": "Which process releases energy?"}],
            "options": [
                {
                    "label": "A",
                    "content": [{"type": "paragraph", "text": "Respiration"}],
                },
                {"label": "B", "content": [{"type": "paragraph", "text": "Osmosis"}]},
                {"label": "C", "content": [{"type": "paragraph", "text": "Diffusion"}]},
                {"label": "D", "content": [{"type": "paragraph", "text": "Excretion"}]},
            ],
        },
        "topic_names": ["Nutrition"],
        "answer": "A. Respiration",
        "source": {"type": "ai_generated", "name": "question-generation"},
    }
    payload.update(overrides)
    return payload


def _create_batch(api_client, *, chapter_slugs=None):
    return api_client.post(
        "/api/bank/generation-batches/",
        {
            "chapter_slugs": chapter_slugs or ["life-processes"],
            "topic_names": ["Nutrition"],
            "difficulty_preset": "balanced",
            "count": 2,
        },
        format="json",
    )


class FakeGenerator:
    payloads: list[dict] = [_payload()]
    boom: Exception | None = None
    requests = []

    def generate(self, request):
        self.__class__.requests.append(request)
        if self.__class__.boom:
            raise self.__class__.boom
        return list(self.__class__.payloads)


def _install_fake_generator(monkeypatch, *, payloads=None, boom=None):
    FakeGenerator.payloads = list(payloads if payloads is not None else [_payload()])
    FakeGenerator.boom = boom
    FakeGenerator.requests = []
    monkeypatch.setattr(drain_mod, "build_generator", lambda: FakeGenerator())
    return FakeGenerator


def test_create_batch_persists_teacher_scope_and_request(api_client, user):
    """The request returns a durable queued job, not generated Questions."""
    resp = _create_batch(api_client)

    assert resp.status_code == 202
    assert resp.data["status"] == GenerationBatchStatus.QUEUED
    assert resp.data["chapter_slugs"] == ["life-processes"]
    assert resp.data["topic_names"] == ["Nutrition"]

    batch = GenerationBatch.objects.get(pk=resp.data["id"])
    assert batch.school == user.school
    assert batch.created_by == user
    assert batch.chapters.get().slug == "life-processes"
    assert batch.difficulty_preset == "balanced"
    assert batch.requested_count == 2
    assert Question.objects.count() == 0


def test_create_batch_enforces_one_active_batch_per_teacher(api_client):
    """A teacher cannot start another review-pending generation batch."""
    first = _create_batch(api_client)
    second = _create_batch(api_client)

    assert first.status_code == 202
    assert second.status_code == 409
    assert "active" in second.data["detail"]


def test_create_batch_rejects_unknown_difficulty_preset(api_client):
    """Unknown difficulty presets fail early instead of silently reshaping intent."""
    resp = api_client.post(
        "/api/bank/generation-batches/",
        {
            "chapter_slugs": ["life-processes"],
            "difficulty_preset": "impossible",
        },
        format="json",
    )

    assert resp.status_code == 400
    assert "difficulty_preset" in resp.data


def test_ready_expired_batch_no_longer_blocks_new_batch(api_client, user):
    """Ready batches expire after 30 days so the active-batch lock clears."""
    batch = GenerationBatch.objects.create(
        school=user.school,
        created_by=user,
        status=GenerationBatchStatus.READY_FOR_REVIEW,
        ready_at=timezone.now() - timedelta(days=31),
    )
    batch.chapters.set([1])

    resp = _create_batch(api_client)

    batch.refresh_from_db()
    assert batch.status == GenerationBatchStatus.EXPIRED
    assert resp.status_code == 202


def test_generation_batch_detail_and_candidates_are_owner_scoped(api_client, user):
    """Polling and candidate review must not reveal another teacher's batch."""
    batch = GenerationBatch.objects.create(
        school=user.school,
        created_by=user,
        status=GenerationBatchStatus.READY_FOR_REVIEW,
    )
    GeneratedQuestionCandidate.objects.create(batch=batch, payload=_payload())

    assert (
        api_client.get(f"/api/bank/generation-batches/{batch.pk}/").status_code == 200
    )
    assert (
        api_client.get(
            f"/api/bank/generation-batches/{batch.pk}/candidates/"
        ).status_code
        == 200
    )

    other_school = School.objects.create(name="Other School")
    other_user = type(user).objects.create_user(
        email="other@example.com", password="pass", school=other_school
    )
    other_client = APIClient()
    other_client.force_authenticate(user=other_user)

    assert (
        other_client.get(f"/api/bank/generation-batches/{batch.pk}/").status_code == 404
    )
    assert (
        other_client.get(
            f"/api/bank/generation-batches/{batch.pk}/candidates/"
        ).status_code
        == 404
    )


def test_drain_generates_valid_candidates_without_inserting_questions(
    db, user, monkeypatch
):
    """The cron persists only review candidates; bank insertion waits for accept."""
    fake = _install_fake_generator(
        monkeypatch,
        payloads=[_payload(), _payload(answer="", raw_text="invalid")],
    )
    batch = GenerationBatch.objects.create(
        school=user.school,
        created_by=user,
        difficulty_preset="balanced",
        requested_count=2,
    )
    batch.chapters.set([1])

    call_command("drain_generation_batches")

    batch.refresh_from_db()
    assert batch.status == GenerationBatchStatus.READY_FOR_REVIEW
    assert batch.ready_at is not None
    assert batch.error == ""
    assert GeneratedQuestionCandidate.objects.count() == 1
    assert Question.objects.count() == 0
    assert fake.requests[0].chapter_slugs == ("life-processes",)
    assert fake.requests[0].topic_names == ()
    assert fake.requests[0].difficulty_targets == {"easy": 30, "medium": 50, "hard": 20}
    assert fake.requests[0].count == 2


def test_drain_records_failure_without_exposing_candidates(db, user, monkeypatch):
    """A generation exception is a failed batch, not a leaked partial review list."""
    _install_fake_generator(monkeypatch, boom=RuntimeError("model unavailable"))
    batch = GenerationBatch.objects.create(school=user.school, created_by=user)
    batch.chapters.set([1])

    call_command("drain_generation_batches")

    batch.refresh_from_db()
    assert batch.status == GenerationBatchStatus.FAILED
    assert "model unavailable" in batch.error
    assert GeneratedQuestionCandidate.objects.count() == 0


def test_accept_ready_batch_inserts_questions_and_marks_candidates(api_client, user):
    """Teacher acceptance is the only path from generated candidate to bank row."""
    batch = GenerationBatch.objects.create(
        school=user.school,
        created_by=user,
        status=GenerationBatchStatus.READY_FOR_REVIEW,
        ready_at=timezone.now(),
    )
    candidate = GeneratedQuestionCandidate.objects.create(
        batch=batch, payload=_payload()
    )

    resp = api_client.post(f"/api/bank/generation-batches/{batch.pk}/accept/")

    assert resp.status_code == 200
    batch.refresh_from_db()
    candidate.refresh_from_db()
    question = Question.objects.get()
    assert batch.status == GenerationBatchStatus.ACCEPTED
    assert candidate.status == GeneratedQuestionCandidateStatus.ACCEPTED
    assert candidate.question == question
    assert question.school == user.school
    assert question.source_type == SourceType.AI_GENERATED
    assert question.answer_source == AnswerSource.GENERATED_UNVERIFIED
    assert question.verified is False
    assert question.chapter.slug == "life-processes"


def test_expiry_marks_unaccepted_candidates_but_preserves_accepted_questions(db, user):
    """The 30-day cleanup only expires unaccepted review work."""
    accepted_batch = GenerationBatch.objects.create(
        school=user.school,
        created_by=user,
        status=GenerationBatchStatus.ACCEPTED,
        ready_at=timezone.now() - timedelta(days=31),
        accepted_at=timezone.now() - timedelta(days=30),
    )
    ready_batch = GenerationBatch.objects.create(
        school=user.school,
        created_by=user,
        status=GenerationBatchStatus.READY_FOR_REVIEW,
        ready_at=timezone.now() - timedelta(days=31),
    )
    candidate = GeneratedQuestionCandidate.objects.create(
        batch=ready_batch, payload=_payload()
    )
    question = Question.objects.create(
        school=user.school,
        chapter_id=1,
        section="A",
        qtype="mcq",
        marks=1,
        text="Accepted generated Question?",
        answer="A",
    )

    expired = GenerationBatch.expire_ready_batches()

    accepted_batch.refresh_from_db()
    ready_batch.refresh_from_db()
    candidate.refresh_from_db()
    question.refresh_from_db()
    assert expired == 1
    assert accepted_batch.status == GenerationBatchStatus.ACCEPTED
    assert ready_batch.status == GenerationBatchStatus.EXPIRED
    assert candidate.status == GeneratedQuestionCandidateStatus.EXPIRED
    assert Question.objects.filter(pk=question.pk).exists()
