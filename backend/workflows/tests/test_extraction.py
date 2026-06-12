"""Resumable-extraction tests: kill a run mid-paper, resume, never re-bill.

These prove #157's payoff — the reason extraction became a ``StateGraph`` at
all. Every paid model call is counted through a fake ``make_chat_model``
factory, so the assertions are literally about money (Rule 13): a resumed
thread must spend calls only on pages the killed run never extracted, and a
re-run persist step must dedup, never duplicate, ``Question`` rows. The
command-level tests pin ADR-0006's split: the drain finds work via the
``IngestionJob`` ledger but trusts the *checkpoint* for how far the thread
got, resuming in-flight jobs by ``thread_id`` rather than restarting them.

Fakes are injected via ``build_extraction_graph(checkpointer, make_model)``
and ``drain_mod.make_chat_model`` — no module-global patching of the graph
(Rules 9/11). The checkpointer is the real ``PostgresSaver`` against the test
database; two ``get_checkpointer()`` blocks share nothing in memory, standing
in for the killed process and the later cron pass.
"""

from __future__ import annotations

import uuid

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command

from bank.management.commands import drain_ingestion_jobs as drain_mod
from bank.models import IngestionJob, IngestionJobStatus, Question
from workflows.checkpointer import get_checkpointer
from workflows.extraction import build_extraction_graph

pytestmark = pytest.mark.django_db


class PageFake:
    """``make_chat_model`` stand-in counting paid calls — acts as both the chat
    model and its structured runnable. Each invoke pops one canned page
    payload; ``fail_on=n`` raises on the n-th call, simulating a run dying
    mid-paper."""

    def __init__(self, payloads=(), fail_on=None):
        self._payloads = list(payloads)
        self.fail_on = fail_on
        self.calls = 0

    def __call__(self, purpose):
        return self

    def with_structured_output(self, schema, method=None):
        return self

    def invoke(self, messages):
        self.calls += 1
        if self.fail_on is not None and self.calls == self.fail_on:
            raise RuntimeError("killed mid-paper")
        return self._payloads.pop(0) if self._payloads else {"questions": []}


def _payload(text):
    return {"questions": [{"qtype": "short_answer", "marks": 3, "rawText": text}]}


def _job():
    return IngestionJob.objects.create(
        pdf=SimpleUploadedFile("31-2-1.pdf", b"%PDF-1.4 stub"),
        source_file_name="31-2-1.pdf",
    )


def _cfg(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


@pytest.fixture
def three_pages(monkeypatch):
    """Make the stub PDF split into three pages — three checkpointed steps."""
    pages = [b"p1", b"p2", b"p3"]
    monkeypatch.setattr("workflows.extraction.count_pages", lambda b: len(pages))
    monkeypatch.setattr("workflows.extraction.slice_page", lambda b, i: pages[i])


def _crash_mid_paper(job, thread_id):
    """First pass: pages 1–2 extracted and checkpointed, the run dies on 3."""
    crashing = PageFake([_payload("Q1"), _payload("Q2")], fail_on=3)
    with get_checkpointer() as checkpointer:
        graph = build_extraction_graph(checkpointer, make_model=crashing)
        with pytest.raises(RuntimeError, match="killed mid-paper"):
            graph.invoke({"job_id": job.pk}, _cfg(thread_id), durability="sync")
    assert crashing.calls == 3
    assert Question.objects.count() == 0  # persist never ran


def test_resume_after_mid_paper_kill_only_bills_unextracted_pages(three_pages):
    """The Rule-13 payoff in one test: a fresh process resuming the thread pays
    for exactly the one page the killed run never extracted — pages 1–2 come
    out of the checkpoint, and the paper still persists complete."""
    job = _job()
    thread_id = uuid.uuid4().hex
    _crash_mid_paper(job, thread_id)

    resumed = PageFake([_payload("Q3")])
    with get_checkpointer() as fresh_checkpointer:
        graph = build_extraction_graph(fresh_checkpointer, make_model=resumed)
        final = graph.invoke(None, _cfg(thread_id), durability="sync")

    assert resumed.calls == 1
    assert final["created"] == 3
    assert set(Question.objects.values_list("text", flat=True)) == {"Q1", "Q2", "Q3"}


def test_rerunning_persist_dedups_instead_of_duplicating(three_pages):
    """A crash between persisting rows and checkpointing re-runs persist on
    resume; the ``source_hash`` dedup means a re-run can only skip. Proven the
    blunt way: a whole second thread over the same job creates zero new rows
    and reports them all as skipped — so any partial re-run can't duplicate
    either."""
    job = _job()
    pages = [_payload("Q1"), _payload("Q2"), _payload("Q3")]
    with get_checkpointer() as checkpointer:
        graph = build_extraction_graph(checkpointer, make_model=PageFake(pages))
        first = graph.invoke(
            {"job_id": job.pk}, _cfg(uuid.uuid4().hex), durability="sync"
        )
    assert first["created"] == 3

    with get_checkpointer() as checkpointer:
        graph = build_extraction_graph(checkpointer, make_model=PageFake(pages))
        second = graph.invoke(
            {"job_id": job.pk}, _cfg(uuid.uuid4().hex), durability="sync"
        )

    assert second["created"] == 0
    assert second["skipped"] == 3
    assert Question.objects.count() == 3


def test_drain_resumes_running_job_by_thread_id(three_pages, monkeypatch):
    """The cron pass after a crash must resume, not restart: the job is still
    ``running`` with a ``thread_id``, so the drain continues that thread —
    one paid call for the missing page — and settles the ledger to done with
    the full paper's counts."""
    job = _job()
    thread_id = uuid.uuid4().hex
    _crash_mid_paper(job, thread_id)
    IngestionJob.objects.filter(pk=job.pk).update(
        status=IngestionJobStatus.RUNNING, thread_id=thread_id
    )

    resumed = PageFake([_payload("Q3")])
    monkeypatch.setattr(drain_mod, "make_chat_model", resumed)
    call_command("drain_ingestion_jobs")

    job.refresh_from_db()
    assert job.status == IngestionJobStatus.DONE
    assert resumed.calls == 1
    assert job.created_count == 3
    assert Question.objects.count() == 3


def test_drain_settles_finished_thread_without_reinvoking(three_pages, monkeypatch):
    """If the crash landed between the graph finishing and the ledger update,
    the thread is complete and only the ledger is stale. The drain must read
    the counts back from the checkpoint — zero model calls, zero new rows —
    not start a paid re-run."""
    job = _job()
    thread_id = uuid.uuid4().hex
    pages = [_payload("Q1"), _payload("Q2"), _payload("Q3")]
    with get_checkpointer() as checkpointer:
        graph = build_extraction_graph(checkpointer, make_model=PageFake(pages))
        graph.invoke({"job_id": job.pk}, _cfg(thread_id), durability="sync")
    IngestionJob.objects.filter(pk=job.pk).update(
        status=IngestionJobStatus.RUNNING, thread_id=thread_id
    )

    silent = PageFake(fail_on=1)  # any model call would blow the test
    monkeypatch.setattr(drain_mod, "make_chat_model", silent)
    call_command("drain_ingestion_jobs")

    job.refresh_from_db()
    assert job.status == IngestionJobStatus.DONE
    assert job.created_count == 3
    assert silent.calls == 0
    assert Question.objects.count() == 3
