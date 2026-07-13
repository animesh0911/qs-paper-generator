"""Optional answer generation for questions extracted from an upload.

These tests exercise the public upload-answer endpoints and the drain seam: the
HTTP request only queues work, while the cron command performs the paid LLM pass
and persists generated answers back onto the extracted ``Question`` rows.
"""

from __future__ import annotations

import json

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import MemorySaver
from rest_framework.test import APIClient

from bank.answer_generation_core import AnswerBatchResult
from bank.management.commands import drain_answer_generation_jobs as drain_mod
from bank.models import (
    AnswerGenerationJob,
    AnswerGenerationJobStatus,
    AnswerSource,
    IngestionJob,
    IngestionJobStatus,
    Question,
)

pytestmark = pytest.mark.django_db


def _pdf_upload(name="31-2-1.pdf"):
    return SimpleUploadedFile(name, b"%PDF-1.4 stub", content_type="application/pdf")


def _done_upload(user) -> IngestionJob:
    return IngestionJob.objects.create(
        school=user.school,
        created_by=user,
        pdf=_pdf_upload(),
        source_file_name="31-2-1.pdf",
        status=IngestionJobStatus.DONE,
    )


def _question(job: IngestionJob, text="Define photosynthesis.", **kwargs) -> Question:
    defaults = {
        "school": job.school,
        "ingestion_job": job,
        "section": "C",
        "qtype": "short_answer",
        "marks": 3,
        "text": text,
        "parse_quality": "clean",
    }
    defaults.update(kwargs)
    return Question.objects.create(**defaults)


class _FakeFactory:
    def __init__(self, answers_by_id: dict[int, str]):
        self.answers_by_id = answers_by_id
        self.build_count = 0

    def __call__(self, purpose):
        self.build_count += 1
        payload = {
            "answers": [
                {"id": qid, "answer": answer}
                for qid, answer in self.answers_by_id.items()
            ]
        }
        return GenericFakeChatModel(
            messages=iter([AIMessage(content=json.dumps(payload))])
        )


def test_teacher_can_queue_answer_generation_for_finished_upload(api_client, user):
    """Clicking Generate answers creates a school-scoped job and returns 202;
    the endpoint itself must not call the LLM."""
    job = _done_upload(user)
    q = _question(job)

    resp = api_client.post(f"/api/bank/ingest/{job.pk}/answers/")

    assert resp.status_code == 202
    assert resp.data["status"] == AnswerGenerationJobStatus.PENDING
    answer_job = AnswerGenerationJob.objects.get(pk=resp.data["id"])
    assert answer_job.ingestion_job == job
    assert answer_job.school == user.school
    assert answer_job.created_by == user
    assert answer_job.total_count == 1
    q.refresh_from_db()
    assert q.answer == ""


def test_answer_generation_requires_finished_extraction(api_client, user):
    job = IngestionJob.objects.create(
        school=user.school,
        created_by=user,
        pdf=_pdf_upload(),
        status=IngestionJobStatus.RUNNING,
    )

    resp = api_client.post(f"/api/bank/ingest/{job.pk}/answers/")

    assert resp.status_code == 409
    assert AnswerGenerationJob.objects.count() == 0


def test_answer_generation_hides_other_schools_uploads_as_404(api_client):
    from accounts.models import School

    other = School.objects.create(name="Other School")
    job = IngestionJob.objects.create(school=other, pdf=_pdf_upload(), status="done")

    resp = api_client.post(f"/api/bank/ingest/{job.pk}/answers/")

    assert resp.status_code == 404


def test_get_answers_returns_job_and_persisted_answers(api_client, user):
    job = _done_upload(user)
    q = _question(
        job,
        answer="Photosynthesis makes glucose using light.",
        answer_source=AnswerSource.GENERATED_UNVERIFIED,
    )
    answer_job = AnswerGenerationJob.objects.create(
        ingestion_job=job,
        school=user.school,
        created_by=user,
        status=AnswerGenerationJobStatus.DONE,
        total_count=1,
        generated_count=1,
    )

    resp = api_client.get(f"/api/bank/ingest/{job.pk}/answers/")

    assert resp.status_code == 200
    assert resp.data["job"]["id"] == answer_job.pk
    assert resp.data["answers"] == [
        {
            "question_id": q.pk,
            "answer": "Photosynthesis makes glucose using light.",
            "answer_source": AnswerSource.GENERATED_UNVERIFIED,
        }
    ]


def test_drain_persists_generated_answers_as_unverified(user, monkeypatch):
    job = _done_upload(user)
    q = _question(job)
    AnswerGenerationJob.objects.create(
        ingestion_job=job,
        school=user.school,
        created_by=user,
        total_count=1,
    )
    factory = _FakeFactory({q.pk: "Photosynthesis converts light energy to food."})
    monkeypatch.setattr(drain_mod, "make_chat_model", factory)

    call_command("drain_answer_generation_jobs")

    q.refresh_from_db()
    assert q.answer == "Photosynthesis converts light energy to food."
    assert q.answer_source == AnswerSource.GENERATED_UNVERIFIED
    answer_job = AnswerGenerationJob.objects.get()
    assert answer_job.status == AnswerGenerationJobStatus.DONE
    assert answer_job.generated_count == 1
    assert factory.build_count == 1


def test_generation_persists_successful_answers_and_skips_missing_output(
    api_client, user, monkeypatch
):
    job = _done_upload(user)
    answered = _question(job, text="Answered question?")
    missing = _question(job, text="Missing question?")
    AnswerGenerationJob.objects.create(
        ingestion_job=job,
        school=user.school,
        created_by=user,
        total_count=2,
    )
    factory = _FakeFactory({answered.pk: "Generated answer."})
    monkeypatch.setattr(drain_mod, "make_chat_model", factory)

    call_command("drain_answer_generation_jobs")

    answered.refresh_from_db()
    missing.refresh_from_db()
    answer_job = AnswerGenerationJob.objects.get()
    assert answered.answer == "Generated answer."
    assert missing.answer == ""
    assert answer_job.status == AnswerGenerationJobStatus.DONE
    assert answer_job.generated_count == 1
    assert answer_job.skipped_count == 1

    response = api_client.get(f"/api/bank/ingest/{job.pk}/answers/")
    assert response.status_code == 200
    assert response.data["job"]["status"] == "done"
    assert response.data["job"]["generated_count"] == 1
    assert response.data["job"]["skipped_count"] == 1
    assert response.data["answers"] == [
        {
            "question_id": answered.pk,
            "answer": "Generated answer.",
            "answer_source": AnswerSource.GENERATED_UNVERIFIED,
        }
    ]


def test_persist_retry_counts_already_written_generated_answer_as_generated(user):
    """A retry of the persist node after answers were written stays idempotent
    and keeps job counts stable instead of converting successes to skips."""
    from bank.answer_generation import persist_generated_answers

    job = _done_upload(user)
    q = _question(job)
    answer_job = AnswerGenerationJob.objects.create(
        ingestion_job=job,
        school=user.school,
        created_by=user,
        total_count=1,
    )
    answers = [{"id": q.pk, "answer": "Stored answer."}]

    first = persist_generated_answers(answer_job, answers)
    second = persist_generated_answers(answer_job, answers)

    assert first == {"generated_count": 1, "skipped_count": 0}
    assert second == {"generated_count": 1, "skipped_count": 0}


def test_upload_answer_generation_can_checkpoint_one_paid_call_per_batch(
    user, monkeypatch
):
    job = _done_upload(user)
    questions = [_question(job, text=f"Question {i}?") for i in range(3)]
    AnswerGenerationJob.objects.create(
        ingestion_job=job,
        school=user.school,
        created_by=user,
        total_count=3,
    )
    factory = _FakeFactory({q.pk: f"Answer {i}." for i, q in enumerate(questions)})
    monkeypatch.setattr(drain_mod, "make_chat_model", factory)

    call_command("drain_answer_generation_jobs", batch_size=1)

    for i, question in enumerate(questions):
        question.refresh_from_db()
        assert question.answer == f"Answer {i}."
    assert factory.build_count == 3
    answer_job = AnswerGenerationJob.objects.get()
    assert answer_job.generated_count == 3
    assert answer_job.skipped_count == 0


def test_answer_graph_resume_does_not_repeat_completed_paid_batches(user):
    from workflows.answer_generation import build_answer_generation_graph

    job = _done_upload(user)
    questions = [_question(job, text=f"Question {i}?") for i in range(3)]
    answer_job = AnswerGenerationJob.objects.create(
        ingestion_job=job,
        school=user.school,
        created_by=user,
        total_count=3,
    )

    class FlakyGenerator:
        def __init__(self):
            self.calls = []
            self.failed_once = False

        def generate(self, question_ids):
            self.calls.append(list(question_ids))
            if question_ids == [questions[1].pk] and not self.failed_once:
                self.failed_once = True
                raise RuntimeError("simulated provider interruption")
            return AnswerBatchResult(
                accepted=tuple(
                    {"id": question_id, "answer": f"Answer for {question_id}."}
                    for question_id in question_ids
                )
            )

    generator = FlakyGenerator()
    checkpointer = MemorySaver()
    config = {"configurable": {"thread_id": "answer-resume-test"}}
    graph = build_answer_generation_graph(
        checkpointer,
        generator_factory=lambda: generator,
        batch_size=1,
    )

    with pytest.raises(RuntimeError, match="simulated provider interruption"):
        graph.invoke({"answer_job_id": answer_job.pk}, config)

    # A new graph simulates a worker restart. Resume from the checkpoint rather
    # than passing initial state again.
    resumed = build_answer_generation_graph(
        checkpointer,
        generator_factory=lambda: generator,
        batch_size=1,
    )
    final = resumed.invoke(None, config)

    assert generator.calls.count([questions[0].pk]) == 1
    assert generator.calls.count([questions[1].pk]) == 2
    assert generator.calls.count([questions[2].pk]) == 1
    assert final["generated_count"] == 3
    for question in questions:
        question.refresh_from_db()
        assert question.answer == f"Answer for {question.pk}."


def test_drain_skips_questions_that_already_have_answers(user, monkeypatch):
    job = _done_upload(user)
    _question(job, answer="Existing.", answer_source=AnswerSource.HUMAN)
    AnswerGenerationJob.objects.create(
        ingestion_job=job,
        school=user.school,
        created_by=user,
        total_count=0,
    )
    factory = _FakeFactory({})
    monkeypatch.setattr(drain_mod, "make_chat_model", factory)

    call_command("drain_answer_generation_jobs")

    answer_job = AnswerGenerationJob.objects.get()
    assert answer_job.status == AnswerGenerationJobStatus.DONE
    assert answer_job.generated_count == 0
    assert answer_job.skipped_count == 1
    assert factory.build_count == 0


def test_answer_generation_requires_authentication(db):
    resp = APIClient().post("/api/bank/ingest/123/answers/")
    assert resp.status_code in (401, 403)
