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
from bank.extraction import _fingerprint
from bank.generation_batches import options_from_generated_content
from bank.management.commands import drain_generation_batches as drain_mod
from bank.models import (
    AnswerSource,
    Chapter,
    GeneratedQuestionCandidate,
    GeneratedQuestionCandidateStatus,
    GenerationBatch,
    GenerationBatchStatus,
    Question,
    SourceType,
)
from corpus.models import (
    ChapterMapNode,
    RetrievalChunk,
    TextbookDocument,
    TextbookElement,
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
        "question_citation_ids": ["chunk-respiration"],
        "answer_citation_ids": ["chunk-respiration"],
        "source": {"type": "ai_generated", "name": "question-generation"},
    }
    payload.update(overrides)
    return payload


def _create_batch(api_client, *, chapter_slugs=None, chapter_map_node_ids=None):
    payload = {
        "chapter_slugs": chapter_slugs or ["life-processes"],
        "topic_names": ["Nutrition"],
        "difficulty_preset": "balanced",
        "count": 2,
    }
    if chapter_map_node_ids is not None:
        payload["chapter_map_node_ids"] = chapter_map_node_ids
    return api_client.post(
        "/api/bank/generation-batches/",
        payload,
        format="json",
    )


def _create_grounded_topic(*, empty=False):
    chapter = Chapter.objects.get(slug="life-processes")
    document = TextbookDocument.objects.create(
        chapter=chapter,
        source_file_name="jesc104.pdf",
        source_hash="hash-grounded-generation",
        extractor_name="test",
        extractor_version="v1",
        canonical_json_path="content/ncert/jesc104.json",
        canonical_json_hash="canonical-grounded-generation",
        page_count=2,
    )
    heading = TextbookElement.objects.create(
        document=document,
        stable_element_id="element-heading",
        element_type="heading",
        source_order=1,
        page_number=1,
        text="Life processes",
    )
    section = ChapterMapNode.objects.create(
        document=document,
        stable_node_id="node-nutrition",
        node_type=ChapterMapNode.NodeType.SECTION,
        title="Nutrition",
        source_element=heading,
        source_start=1,
        source_end=2,
        page_start=1,
        page_end=2,
        element_count=2,
    )
    if not empty:
        RetrievalChunk.objects.create(
            document=document,
            chapter=chapter,
            chapter_map_node=section,
            stable_chunk_id="chunk-respiration",
            text="Respiration releases energy from glucose in living cells.",
            source_element_ids=["element-2"],
            page_start=2,
            page_end=2,
            content_types=["paragraph"],
            citation={
                "chapter_slug": chapter.slug,
                "chapter_map_node_id": section.stable_node_id,
                "source_element_ids": ["element-2"],
                "pages": [2],
            },
        )
    return section


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


def test_create_batch_rejects_topic_nodes_from_more_than_one_chapter(api_client):
    """The MVP allows exactly one Chapter when topic node ids are present."""
    node = _create_grounded_topic()

    resp = api_client.post(
        "/api/bank/generation-batches/",
        {
            "chapter_slugs": ["life-processes", "electricity"],
            "chapter_map_node_ids": [node.stable_node_id],
            "difficulty_preset": "balanced",
        },
        format="json",
    )

    assert resp.status_code == 400
    assert "exactly one chapter_slug" in str(resp.data)


def test_create_batch_allows_multiple_queued_batches_fifo(api_client):
    """Teachers may queue several batches at once; they line up FIFO."""
    first = _create_batch(api_client)
    second = _create_batch(api_client)

    assert first.status_code == 202
    assert second.status_code == 202

    listed = api_client.get("/api/bank/generation-batches/")
    assert listed.status_code == 200
    ids = [row["id"] for row in listed.data]
    assert ids == [first.data["id"], second.data["id"]]


def test_create_batch_enforces_queue_cap(api_client, user):
    """The per-teacher non-terminal cap bounds paid model-call runaway."""
    from bank.models import MAX_ACTIVE_GENERATION_BATCHES_PER_TEACHER

    for _ in range(MAX_ACTIVE_GENERATION_BATCHES_PER_TEACHER):
        assert _create_batch(api_client).status_code == 202

    overflow = _create_batch(api_client)
    assert overflow.status_code == 409
    assert "full" in overflow.data["detail"]


def test_discard_ready_batch_frees_a_queue_slot(api_client, user):
    """Discarding a ready batch marks its candidates discarded and clears it."""
    batch = GenerationBatch.objects.create(
        school=user.school,
        created_by=user,
        status=GenerationBatchStatus.READY_FOR_REVIEW,
        ready_at=timezone.now(),
    )
    batch.chapters.set([Chapter.objects.get(slug="life-processes")])
    candidate = batch.candidates.create(payload=_payload())

    resp = api_client.post(f"/api/bank/generation-batches/{batch.pk}/discard/")

    assert resp.status_code == 200
    assert resp.data["status"] == GenerationBatchStatus.DISCARDED
    batch.refresh_from_db()
    candidate.refresh_from_db()
    assert batch.status == GenerationBatchStatus.DISCARDED
    assert candidate.status == GeneratedQuestionCandidateStatus.DISCARDED
    assert Question.objects.count() == 0


def test_discard_rejects_in_flight_batch(api_client, user):
    """A batch the worker may be running cannot be discarded mid-run."""
    batch = GenerationBatch.objects.create(
        school=user.school,
        created_by=user,
        status=GenerationBatchStatus.GENERATING_QUESTIONS,
    )
    batch.chapters.set([Chapter.objects.get(slug="life-processes")])

    resp = api_client.post(f"/api/bank/generation-batches/{batch.pk}/discard/")

    assert resp.status_code == 409
    batch.refresh_from_db()
    assert batch.status == GenerationBatchStatus.GENERATING_QUESTIONS


def test_retry_requeues_a_failed_batch(api_client, user):
    """Retry flips a failed batch back to queued (keeping its checkpoint pointer)
    so the drainer runs it again."""
    batch = GenerationBatch.objects.create(
        school=user.school,
        created_by=user,
        status=GenerationBatchStatus.FAILED,
        error="Model returned no valid candidates.",
        thread_id="gen:abc123",
    )
    batch.chapters.set([Chapter.objects.get(slug="life-processes")])

    resp = api_client.post(f"/api/bank/generation-batches/{batch.pk}/retry/")

    assert resp.status_code == 202
    batch.refresh_from_db()
    assert batch.status == GenerationBatchStatus.QUEUED
    assert batch.error == ""
    assert batch.thread_id == "gen:abc123"  # resume, not restart


def test_retry_rejects_a_non_failed_batch(api_client, user):
    """Only a failed batch is retryable — no accidental re-bill of live work."""
    batch = GenerationBatch.objects.create(
        school=user.school,
        created_by=user,
        status=GenerationBatchStatus.GENERATING_QUESTIONS,
    )
    batch.chapters.set([Chapter.objects.get(slug="life-processes")])

    resp = api_client.post(f"/api/bank/generation-batches/{batch.pk}/retry/")

    assert resp.status_code == 409
    batch.refresh_from_db()
    assert batch.status == GenerationBatchStatus.GENERATING_QUESTIONS


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


def test_create_batch_persists_selected_chapter_map_node(api_client):
    """Grounded generation scope uses canonical ChapterMapNode ids, not topics."""
    section = _create_grounded_topic()

    resp = _create_batch(api_client, chapter_map_node_ids=[section.stable_node_id])

    assert resp.status_code == 202
    assert resp.data["chapter_map_node_ids"] == ["node-nutrition"]
    batch = GenerationBatch.objects.get(pk=resp.data["id"])
    assert batch.chapter_map_node_ids == ["node-nutrition"]


def test_ready_expired_batch_no_longer_blocks_new_batch(api_client, user):
    """Ready batches expire after 30 days so the active-batch lock clears."""
    batch = GenerationBatch.objects.create(
        school=user.school,
        created_by=user,
        status=GenerationBatchStatus.READY_FOR_REVIEW,
        ready_at=timezone.now() - timedelta(days=31),
    )
    batch.chapters.set([Chapter.objects.get(slug="life-processes")])

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
    batch.chapters.set([Chapter.objects.get(slug="life-processes")])

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
    batch.chapters.set([Chapter.objects.get(slug="life-processes")])

    call_command("drain_generation_batches")

    batch.refresh_from_db()
    assert batch.status == GenerationBatchStatus.FAILED
    assert "model unavailable" in batch.error
    assert GeneratedQuestionCandidate.objects.count() == 0


def test_drain_sanitises_raw_provider_error_on_the_batch(db, user, monkeypatch):
    """A raw provider 402 dump must never land on the teacher-visible batch —
    it carries account ids and billing URLs. Only actionable copy is stored."""
    raw = (
        "Error code: 402 - {'error': {'message': 'This request requires more "
        "credits'}, 'user_id': 'user_SECRET'}"
    )
    _install_fake_generator(monkeypatch, boom=RuntimeError(raw))
    batch = GenerationBatch.objects.create(school=user.school, created_by=user)
    batch.chapters.set([Chapter.objects.get(slug="life-processes")])

    call_command("drain_generation_batches")

    batch.refresh_from_db()
    assert batch.status == GenerationBatchStatus.FAILED
    assert "credits" in batch.error.lower()
    assert "user_SECRET" not in batch.error
    assert "{" not in batch.error


def test_grounded_batch_persists_manifest_and_sends_one_grounded_request(
    db, user, monkeypatch
):
    """Selected ChapterMapNode generation is grounded by one corpus manifest."""
    section = _create_grounded_topic()
    fake = _install_fake_generator(monkeypatch, payloads=[_payload()])
    batch = GenerationBatch.objects.create(
        school=user.school,
        created_by=user,
        difficulty_preset="balanced",
        requested_count=2,
        chapter_map_node_ids=[section.stable_node_id],
    )
    batch.chapters.set([section.document.chapter])

    call_command("drain_generation_batches")

    batch.refresh_from_db()
    candidate = GeneratedQuestionCandidate.objects.get()
    manifest = candidate.grounding_manifest
    assert batch.status == GenerationBatchStatus.READY_FOR_REVIEW
    assert len(fake.requests) == 1
    assert fake.requests[0].grounding_manifest == manifest
    assert manifest["requested_chapter_map_node_ids"] == ["node-nutrition"]
    assert manifest["excerpts"][0]["citation_id"] == "chunk-respiration"
    assert manifest["excerpts"][0]["text"] == (
        "Respiration releases energy from glucose in living cells."
    )
    assert manifest["diagnostics"]["cap_reached"] is False


def test_grounded_batch_refuses_generation_when_context_is_empty(db, user, monkeypatch):
    """No paid/model seam call is made when the selected topic has no excerpts."""
    section = _create_grounded_topic(empty=True)
    fake = _install_fake_generator(monkeypatch, payloads=[_payload()])
    batch = GenerationBatch.objects.create(
        school=user.school,
        created_by=user,
        chapter_map_node_ids=[section.stable_node_id],
    )
    batch.chapters.set([section.document.chapter])

    call_command("drain_generation_batches")

    batch.refresh_from_db()
    assert batch.status == GenerationBatchStatus.FAILED
    assert "No grounded NCERT context" in batch.error
    assert fake.requests == []
    assert GeneratedQuestionCandidate.objects.count() == 0


def test_grounded_batch_rejects_unknown_citations(db, user, monkeypatch):
    """Generated candidates must cite only excerpts supplied in the manifest."""
    section = _create_grounded_topic()
    _install_fake_generator(
        monkeypatch,
        payloads=[
            _payload(
                question_citation_ids=["unknown-chunk"],
                answer_citation_ids=["chunk-respiration"],
            )
        ],
    )
    batch = GenerationBatch.objects.create(
        school=user.school,
        created_by=user,
        chapter_map_node_ids=[section.stable_node_id],
    )
    batch.chapters.set([section.document.chapter])

    call_command("drain_generation_batches")

    batch.refresh_from_db()
    assert batch.status == GenerationBatchStatus.FAILED
    assert "No valid generated candidates" in batch.error
    assert GeneratedQuestionCandidate.objects.count() == 0


def test_options_from_generated_content_handles_null_option_content():
    """Accept conversion is defensive even if legacy bad candidate JSON exists."""
    payload = _payload()
    payload["content"]["options"][0]["content"] = None

    options = options_from_generated_content(payload)

    assert options[0] == {"label": "A", "text": ""}
    assert options[1] == {"label": "B", "text": "Osmosis"}


def test_accept_ready_batch_inserts_selected_questions_and_rejects_rest(
    api_client, user
):
    """Teacher acceptance imports selected candidates and audits rejected ones."""
    batch = GenerationBatch.objects.create(
        school=user.school,
        created_by=user,
        status=GenerationBatchStatus.READY_FOR_REVIEW,
        ready_at=timezone.now(),
    )
    accepted_candidate = GeneratedQuestionCandidate.objects.create(
        batch=batch, payload=_payload(raw_text="Accepted generated Question?")
    )
    rejected_candidate = GeneratedQuestionCandidate.objects.create(
        batch=batch, payload=_payload(raw_text="Rejected generated Question?")
    )

    resp = api_client.post(
        f"/api/bank/generation-batches/{batch.pk}/accept/",
        {"accepted_candidate_ids": [accepted_candidate.pk]},
        format="json",
    )

    assert resp.status_code == 200
    batch.refresh_from_db()
    accepted_candidate.refresh_from_db()
    rejected_candidate.refresh_from_db()
    question = Question.objects.get()
    assert batch.status == GenerationBatchStatus.ACCEPTED
    assert accepted_candidate.status == GeneratedQuestionCandidateStatus.ACCEPTED
    assert accepted_candidate.question == question
    assert accepted_candidate.accepted_at is not None
    assert rejected_candidate.status == GeneratedQuestionCandidateStatus.REJECTED
    assert rejected_candidate.question is None
    assert rejected_candidate.rejected_at is not None
    assert question.text == "Accepted generated Question?"
    assert question.school == user.school
    assert question.source_type == SourceType.AI_GENERATED
    assert question.source_hash == _fingerprint("Accepted generated Question?")
    assert question.answer_source == AnswerSource.GENERATED_UNVERIFIED
    assert question.verified is False
    assert question.chapter.slug == "life-processes"


def test_accept_ready_batch_preserves_grounding_provenance(api_client, user):
    """Accepted AI questions keep audit citations from the reviewed candidate."""
    batch = GenerationBatch.objects.create(
        school=user.school,
        created_by=user,
        status=GenerationBatchStatus.READY_FOR_REVIEW,
        ready_at=timezone.now(),
    )
    candidate = GeneratedQuestionCandidate.objects.create(
        batch=batch,
        payload=_payload(),
        grounding_manifest={
            "excerpts": [
                {
                    "citation_id": "chunk-respiration",
                    "text": "Respiration releases energy from glucose.",
                },
                {"citation_id": "unused", "text": "Not cited."},
            ]
        },
    )

    resp = api_client.post(
        f"/api/bank/generation-batches/{batch.pk}/accept/",
        {"accepted_candidate_ids": [candidate.pk]},
        format="json",
    )

    assert resp.status_code == 200
    provenance = Question.objects.get().content["__provenance"]
    assert provenance["batchId"] == batch.pk
    assert provenance["candidateId"] == candidate.pk
    assert provenance["questionCitationIds"] == ["chunk-respiration"]
    assert provenance["answerCitationIds"] == ["chunk-respiration"]
    assert provenance["groundingExcerpts"] == [
        {
            "citation_id": "chunk-respiration",
            "text": "Respiration releases energy from glucose.",
        }
    ]


def test_accept_ready_batch_rejects_empty_selection_without_side_effects(
    api_client, user
):
    """A teacher cannot complete review when no candidates remain accepted."""
    batch = GenerationBatch.objects.create(
        school=user.school,
        created_by=user,
        status=GenerationBatchStatus.READY_FOR_REVIEW,
        ready_at=timezone.now(),
    )
    candidate = GeneratedQuestionCandidate.objects.create(
        batch=batch, payload=_payload()
    )

    resp = api_client.post(
        f"/api/bank/generation-batches/{batch.pk}/accept/",
        {"accepted_candidate_ids": []},
        format="json",
    )

    assert resp.status_code == 400
    batch.refresh_from_db()
    candidate.refresh_from_db()
    assert batch.status == GenerationBatchStatus.READY_FOR_REVIEW
    assert candidate.status == GeneratedQuestionCandidateStatus.READY_FOR_REVIEW
    assert Question.objects.count() == 0


def test_accept_ready_batch_rejects_unknown_or_foreign_candidate_ids(api_client, user):
    """The selected ids must be ready candidates from this owned batch."""
    batch = GenerationBatch.objects.create(
        school=user.school,
        created_by=user,
        status=GenerationBatchStatus.READY_FOR_REVIEW,
        ready_at=timezone.now(),
    )
    candidate = GeneratedQuestionCandidate.objects.create(
        batch=batch, payload=_payload()
    )

    resp = api_client.post(
        f"/api/bank/generation-batches/{batch.pk}/accept/",
        {"accepted_candidate_ids": [candidate.pk + 1000]},
        format="json",
    )

    assert resp.status_code == 400
    candidate.refresh_from_db()
    assert candidate.status == GeneratedQuestionCandidateStatus.READY_FOR_REVIEW
    assert Question.objects.count() == 0


def test_accept_batch_is_owner_scoped_and_must_still_be_ready(api_client, user):
    """Foreign, failed, and expired batches cannot be partially accepted."""
    expired = GenerationBatch.objects.create(
        school=user.school,
        created_by=user,
        status=GenerationBatchStatus.READY_FOR_REVIEW,
        ready_at=timezone.now() - timedelta(days=31),
    )
    expired_candidate = GeneratedQuestionCandidate.objects.create(
        batch=expired, payload=_payload()
    )
    failed = GenerationBatch.objects.create(
        school=user.school,
        created_by=user,
        status=GenerationBatchStatus.FAILED,
    )
    failed_candidate = GeneratedQuestionCandidate.objects.create(
        batch=failed, payload=_payload()
    )
    other_school = School.objects.create(name="Other School for accept")
    other_user = type(user).objects.create_user(
        email="accept-other@example.com", password="pass", school=other_school
    )
    foreign = GenerationBatch.objects.create(
        school=other_school,
        created_by=other_user,
        status=GenerationBatchStatus.READY_FOR_REVIEW,
        ready_at=timezone.now(),
    )
    foreign_candidate = GeneratedQuestionCandidate.objects.create(
        batch=foreign, payload=_payload()
    )

    expired_resp = api_client.post(
        f"/api/bank/generation-batches/{expired.pk}/accept/",
        {"accepted_candidate_ids": [expired_candidate.pk]},
        format="json",
    )
    failed_resp = api_client.post(
        f"/api/bank/generation-batches/{failed.pk}/accept/",
        {"accepted_candidate_ids": [failed_candidate.pk]},
        format="json",
    )
    foreign_resp = api_client.post(
        f"/api/bank/generation-batches/{foreign.pk}/accept/",
        {"accepted_candidate_ids": [foreign_candidate.pk]},
        format="json",
    )

    assert expired_resp.status_code == 409
    assert failed_resp.status_code == 409
    assert foreign_resp.status_code == 404
    assert Question.objects.count() == 0


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
        chapter=Chapter.objects.get(slug="life-processes"),
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
