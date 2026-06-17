"""drain_ai_jobs lifecycle.

These prove the job-drain contract without any model call (Rule 13): a pending
job is claimed and run via an injected handler, a stale ``base_revision`` is
cancelled *before* the handler is invoked (the cost guard), a handler error
fails only its own job, and ``--dry-run`` touches nothing.
"""

import pytest
from django.core.management import call_command

from ai_editor.management.commands.drain_ai_jobs import Command
from ai_editor.models import AIJob, AIJobKind, AIJobStatus
from papers.models import Paper

pytestmark = pytest.mark.django_db


@pytest.fixture
def paper(user):
    return Paper.objects.create(created_by=user, title="Science — Mock", revision=2)


def _pending(paper, *, kind=AIJobKind.REVIEW, base_revision=2):
    return AIJob.objects.create(
        paper=paper, kind=kind, base_revision=base_revision, status=AIJobStatus.PENDING
    )


def _drain(handlers=None, **options):
    cmd = Command()
    if handlers is not None:
        cmd.handlers = handlers
    call_command(cmd, **options)
    return cmd


def test_drain_runs_a_pending_job_via_its_handler(paper):
    job = _pending(paper)
    calls = []

    def handler(j):
        calls.append(j.pk)
        return {"status": "review", "summary": "ok"}

    _drain(handlers={kind.value: handler for kind in AIJobKind})

    job.refresh_from_db()
    assert calls == [job.pk]
    assert job.status == AIJobStatus.DONE
    assert job.result == {"status": "review", "summary": "ok"}


def test_stale_base_revision_is_cancelled_before_any_handler_call(paper):
    # The paper moved on (revision 2 -> 5) while the job sat queued. The drain
    # must cancel WITHOUT calling the handler — otherwise it spends paid tokens
    # on a proposal that would only be rejected on apply (Rule 13).
    job = _pending(paper, base_revision=2)
    Paper.objects.filter(pk=paper.pk).update(revision=5)

    def handler(_j):
        raise AssertionError("handler must not run for a stale job")

    _drain(handlers={kind.value: handler for kind in AIJobKind})

    job.refresh_from_db()
    assert job.status == AIJobStatus.CANCELLED
    assert job.result is None


def test_one_failing_job_does_not_abort_the_drain(paper, user):
    other_paper = Paper.objects.create(created_by=user, title="Other", revision=0)
    bad = _pending(paper)
    good = _pending(other_paper, base_revision=0)

    def handler(j):
        if j.pk == bad.pk:
            raise ValueError("boom")
        return {"ok": True}

    _drain(handlers={kind.value: handler for kind in AIJobKind})

    bad.refresh_from_db()
    good.refresh_from_db()
    assert bad.status == AIJobStatus.FAILED and "boom" in bad.error
    assert good.status == AIJobStatus.DONE


def test_reclaimed_running_job_is_failed_not_re_run(paper):
    # A row left RUNNING by a crashed drain must not stay stuck (that would lock
    # the paper at 409 forever). A later pass reclaims it and fails it WITHOUT
    # calling the handler — editor jobs have no checkpoint, so re-running would
    # re-bill (Rule 13).
    job = AIJob.objects.create(
        paper=paper,
        kind=AIJobKind.REVIEW,
        base_revision=paper.revision,
        status=AIJobStatus.RUNNING,
    )

    def handler(_j):
        raise AssertionError("handler must not run for a reclaimed running job")

    _drain(handlers={kind.value: handler for kind in AIJobKind})

    job.refresh_from_db()
    assert job.status == AIJobStatus.FAILED
    assert "reclaimed" in job.error.lower()


def test_default_handlers_are_stubbed_until_later_issues(paper):
    # No handler injected: the real registry is stubbed, so the job fails with a
    # clear message rather than silently doing nothing or calling a model.
    job = _pending(paper)

    _drain()

    job.refresh_from_db()
    assert job.status == AIJobStatus.FAILED
    assert "not implemented" in job.error.lower()


def test_dry_run_claims_nothing(paper):
    job = _pending(paper)

    _drain(dry_run=True)

    job.refresh_from_db()
    assert job.status == AIJobStatus.PENDING
