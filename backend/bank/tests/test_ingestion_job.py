"""Tests for the live HTTP ingest front door (issue #104).

Covers the teacher upload endpoint (202 + queued ``IngestionJob``, school
scoping, caller-supplied ``source_type``, permission gate), the status-poll
endpoint (own-school only), the ``drain_ingestion_jobs`` command (a fake
``make_chat_model`` at the seam — no live Gemini; the drain runs the real
extraction graph against the real checkpointer, #157), and that the
``Ingestor`` scopes persisted rows to ``school``. WHY each test matters is in
its docstring. Resume/idempotency mechanics of the graph itself live in
``workflows.tests.test_extraction``.
"""

from __future__ import annotations

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from rest_framework.test import APIClient

from bank.ingestor import Ingestor
from bank.management.commands import drain_ingestion_jobs as drain_mod
from bank.models import (
    IngestionJob,
    IngestionJobStatus,
    Question,
    SourceType,
)

# ---------------------------------------------------------------------------
# Test doubles — no live Gemini, no fitz
# ---------------------------------------------------------------------------


def _q(text="What is photosynthesis?", section="C", qtype="short_answer", marks=3):
    return {
        "section": section,
        "qtype": qtype,
        "marks": marks,
        "text": text,
        "options": [],
        "content": {},
        "chapter_slug": None,
        "cognitive_level": "U",
        "topic_names": [],
        "primary_form": "none",
        "figures": [],
    }


class StubExtractor:
    """Returns canned question dicts; never calls an LLM."""

    def __init__(self, questions):
        self._questions = questions

    def extract(self, pdf_bytes):
        return [dict(q) for q in self._questions]


class SeamFake:
    """``make_chat_model`` stand-in at the drain seam — acts as both the chat
    model and its structured runnable; each invoke pops one canned page
    payload (``boom=True`` raises instead). No provider package, no network."""

    def __init__(self, payloads=(), boom=False):
        self._payloads = list(payloads)
        self.boom = boom
        self.calls = 0

    def __call__(self, purpose):
        return self

    def with_structured_output(self, schema, method=None):
        return self

    def invoke(self, messages):
        self.calls += 1
        if self.boom:
            raise RuntimeError("extraction blew up")
        return self._payloads.pop(0) if self._payloads else {"questions": []}


def _page_payload(text="What is photosynthesis?"):
    """One raw per-page model payload (pre-coercion shape)."""
    return {"questions": [{"qtype": "short_answer", "marks": 3, "rawText": text}]}


class StubCropper:
    """No-op cropper — one ``None`` primary asset per row, no fitz."""

    def crop(self, pdf_bytes, rows, fingerprints):
        return [None] * len(rows)


def _pdf_upload(name="31-2-1.pdf"):
    return SimpleUploadedFile(name, b"%PDF-1.4 stub", content_type="application/pdf")


# ---------------------------------------------------------------------------
# Upload endpoint — POST /api/bank/ingest/
# ---------------------------------------------------------------------------


def test_upload_queues_job_scoped_to_school_and_returns_202(api_client, user):
    """Upload must NOT extract in-request: it queues a pending job (202) scoped
    to the teacher's school, so a multi-page scan can't hang the request and one
    school's upload can't pollute another's bank."""
    resp = api_client.post(
        "/api/bank/ingest/",
        {"pdf": _pdf_upload(), "source_type": "sample_paper"},
        format="multipart",
    )

    assert resp.status_code == 202
    assert resp.data["status"] == IngestionJobStatus.PENDING
    assert resp.data["source_type"] == "sample_paper"

    job = IngestionJob.objects.get(pk=resp.data["id"])
    assert job.school == user.school
    assert job.created_by == user
    assert job.source_file_name == "31-2-1.pdf"
    # No questions created yet — extraction is deferred to the drain command.
    assert Question.objects.count() == 0


def test_upload_defaults_source_type_to_previous_year_paper(api_client):
    """Omitted ``source_type`` falls back to the contract default, not an error."""
    resp = api_client.post(
        "/api/bank/ingest/", {"pdf": _pdf_upload()}, format="multipart"
    )
    assert resp.status_code == 202
    assert resp.data["source_type"] == SourceType.PREVIOUS_YEAR_PAPER


def test_upload_rejects_unknown_source_type(api_client):
    """``source_type`` is caller-supplied but constrained to the known set —
    a typo must 400, not silently land a bogus provenance value."""
    resp = api_client.post(
        "/api/bank/ingest/",
        {"pdf": _pdf_upload(), "source_type": "made_up"},
        format="multipart",
    )
    assert resp.status_code == 400
    assert "source_type" in resp.data


def test_upload_requires_pdf(api_client):
    """A missing file is a client error, not a server-side None deref."""
    resp = api_client.post("/api/bank/ingest/", {}, format="multipart")
    assert resp.status_code == 400
    assert "pdf" in resp.data


def test_upload_forbidden_without_school(db):
    """A teacher signal is school membership (no role field in V1). A user with
    no school can't scope an upload, so the endpoint must refuse — otherwise the
    row would land school-less in a shared bank."""
    from accounts.models import User

    schoolless = User.objects.create_user(email="noschool@example.com", password="pass")
    client = APIClient()
    client.force_authenticate(user=schoolless)
    resp = client.post("/api/bank/ingest/", {"pdf": _pdf_upload()}, format="multipart")
    assert resp.status_code == 403


def test_upload_requires_authentication(db):
    """Anonymous uploads are rejected — the bank is not world-writable."""
    resp = APIClient().post(
        "/api/bank/ingest/", {"pdf": _pdf_upload()}, format="multipart"
    )
    assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Status endpoint — GET /api/bank/ingest/{id}/
# ---------------------------------------------------------------------------


def test_status_returns_own_jobs_progress(api_client, user):
    """The frontend polls this for the result; it must surface status + counts."""
    job = IngestionJob.objects.create(
        school=user.school,
        created_by=user,
        pdf=_pdf_upload(),
        source_file_name="31-2-1.pdf",
        status=IngestionJobStatus.DONE,
        created_count=7,
        skipped_count=2,
    )
    resp = api_client.get(f"/api/bank/ingest/{job.pk}/")
    assert resp.status_code == 200
    assert resp.data["status"] == "done"
    assert resp.data["created_count"] == 7
    assert resp.data["skipped_count"] == 2


def test_status_does_not_expose_thread_id(api_client, user):
    """``thread_id`` is the execution-state pointer (ADR-0006) — checkpointer
    internals, not job status. The poll shape must stay a plain ledger read, so
    adding the field (#157) must not leak it to clients."""
    job = IngestionJob.objects.create(
        school=user.school,
        created_by=user,
        pdf=_pdf_upload(),
        source_file_name="31-2-1.pdf",
        thread_id="abc123",
    )
    resp = api_client.get(f"/api/bank/ingest/{job.pk}/")
    assert resp.status_code == 200
    assert "thread_id" not in resp.data


def test_status_hides_other_schools_jobs_as_404(api_client):
    """Tenancy: a teacher must not even learn another school's job exists, so a
    cross-school id is 404 (not 403)."""
    from accounts.models import School

    other = School.objects.create(name="Other School")
    job = IngestionJob.objects.create(
        school=other, pdf=_pdf_upload(), source_file_name="x.pdf"
    )
    resp = api_client.get(f"/api/bank/ingest/{job.pk}/")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# drain_ingestion_jobs — the cron drainer
# ---------------------------------------------------------------------------


def test_drain_processes_pending_job_into_bank(db, user, monkeypatch):
    """The drain is the only place questions actually enter the bank on the HTTP
    path. A drained job must persist rows scoped to its school, record the
    result counts the teacher polls for, and gain the ``thread_id`` pointer
    that makes a later resume possible (ADR-0006)."""
    monkeypatch.setattr(drain_mod, "make_chat_model", SeamFake([_page_payload()]))
    job = IngestionJob.objects.create(
        school=user.school,
        created_by=user,
        pdf=_pdf_upload(),
        source_file_name="31-2-1.pdf",
        source_type=SourceType.SAMPLE_PAPER,
    )

    call_command("drain_ingestion_jobs")

    job.refresh_from_db()
    assert job.status == IngestionJobStatus.DONE
    assert job.created_count == 1
    assert job.thread_id  # the ledger now points at its graph thread
    q = Question.objects.get()
    assert q.school == user.school
    assert q.source_type == SourceType.SAMPLE_PAPER
    assert q.verified is False


def test_drain_records_failure_without_aborting(db, user, monkeypatch):
    """One bad PDF must not crash the whole cron run — the job is marked failed
    with the error so the teacher sees why, and the drain stays drainable."""
    monkeypatch.setattr(drain_mod, "make_chat_model", SeamFake(boom=True))
    job = IngestionJob.objects.create(
        school=user.school, pdf=_pdf_upload(), source_file_name="bad.pdf"
    )

    call_command("drain_ingestion_jobs")

    job.refresh_from_db()
    assert job.status == IngestionJobStatus.FAILED
    assert "extraction blew up" in job.error
    assert Question.objects.count() == 0


def test_drain_dry_run_makes_no_changes(db, user, monkeypatch):
    """``--dry-run`` is the Rule 13 safety valve: it must never build a model,
    never open the checkpointer, and never touch the job."""

    def _boom(*args, **kwargs):
        raise AssertionError("dry-run must not touch the graph runtime")

    monkeypatch.setattr(drain_mod, "make_chat_model", _boom)
    monkeypatch.setattr(drain_mod, "get_checkpointer", _boom)
    job = IngestionJob.objects.create(
        school=user.school, pdf=_pdf_upload(), source_file_name="x.pdf"
    )

    call_command("drain_ingestion_jobs", "--dry-run")

    job.refresh_from_db()
    assert job.status == IngestionJobStatus.PENDING


# ---------------------------------------------------------------------------
# Ingestor school scoping (unit)
# ---------------------------------------------------------------------------


def test_ingestor_scopes_persisted_rows_to_school(db, user):
    """The tenancy guarantee lives in the coordinator: a school passed to
    ``ingest`` must reach every persisted ``Question.school``."""
    ingestor = Ingestor(extractor=StubExtractor([_q()]), cropper=StubCropper())

    result = ingestor.ingest(b"%PDF", source_file_name="31-2-1.pdf", school=user.school)

    assert result.created == 1
    assert Question.objects.get().school == user.school


def test_ingestor_leaves_school_null_for_cli_path(db):
    """The committed-JSON CLI path passes no school — rows stay tenant-shared,
    so the two front doors don't collide."""
    ingestor = Ingestor(extractor=StubExtractor([_q()]), cropper=StubCropper())

    ingestor.ingest(b"%PDF", source_file_name="31-2-1.pdf")

    assert Question.objects.get().school is None
