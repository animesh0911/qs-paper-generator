"""AI editor async job ledger.

PRD #30 gives the paper editor live AI help (summary, review, scoped edit
proposals). Those are long-running paid model calls, so they do not run inside
the HTTP request: a job-creating endpoint persists an ``AIJob`` row with
``status=pending`` and returns 202 + the job id immediately, and a cron-run
``drain_ai_jobs`` management command drives the row out-of-request — the same
Redis/Celery-free pattern as ``bank.IngestionJob`` + ``drain_ingestion_jobs``
(#104). This reverses the original "Redis/Celery memory only, no persisted
``AIJob``" design, which #105/#106 made infeasible by removing Redis+Celery from
the stack (#107).

Patterns / invariants:
- One active (``pending``/``running``) job per **paper** at a time — enforced by
  the job-creating views, not a DB constraint, under ``select_for_update`` on
  the paper.
- ``base_revision`` snapshots ``Paper.revision`` at creation. The drain cancels
  a job whose ``base_revision`` no longer matches the paper before spending any
  paid tokens (Rule 13) — a paper edited while the job was queued would only
  reject the resulting proposal on apply.
- ``synchronous`` editor surfaces (typed-intent classification, chat) answer in
  the request and never create a row; only summary/review/editor-edit/refine do.

Where it fits:
- Written by: ``ai_editor.views`` (create) and ``drain_ai_jobs`` (drive).
- Polled via: ``GET /api/ai/jobs/{jobId}/`` (``ai_editor.serializers``).
"""

from django.conf import settings
from django.db import models

from papers.models import Paper


class AIJobStatus(models.TextChoices):
    """Lifecycle of an out-of-request editor AI job.

    ``pending`` rows are claimed by ``drain_ai_jobs`` (cron), flipped to
    ``running`` while the model call runs, then ``done`` (with ``result``) or
    ``failed`` (with ``error``). ``cancelled`` is terminal and set without any
    model call when the job's ``base_revision`` is already stale.
    """

    PENDING = "pending", "Pending"
    RUNNING = "running", "Running"
    DONE = "done", "Done"
    FAILED = "failed", "Failed"
    CANCELLED = "cancelled", "Cancelled"


# Non-terminal statuses — used for the one-active-job-per-paper guard and the
# drain's claim filter.
ACTIVE_AI_JOB_STATUSES = (AIJobStatus.PENDING, AIJobStatus.RUNNING)


class AIJobKind(models.TextChoices):
    """Which job-creating endpoint produced the row.

    The drain dispatches on this to the matching handler; the poll result shape
    is endpoint-specific (summary/review are read-only, editor-edit/refine carry
    a scoped proposal).
    """

    SUMMARY = "summary", "Summarize paper"
    REVIEW = "review", "Review paper"
    EDITOR_EDIT = "editor_edit", "Editor edit proposal"
    REFINE = "refine", "Refine editor edit proposal"


class AIJob(models.Model):
    """A queued editor AI request, drained out-of-request into a result.

    See the module docstring for the lifecycle and the ``base_revision``
    cost-guard invariant.
    """

    paper = models.ForeignKey(
        Paper,
        on_delete=models.CASCADE,
        related_name="ai_jobs",
    )
    # Who asked. SET_NULL so deleting a teacher does not drop their jobs.
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ai_jobs",
    )
    kind = models.CharField(max_length=16, choices=AIJobKind.choices)
    status = models.CharField(
        max_length=10,
        choices=AIJobStatus.choices,
        default=AIJobStatus.PENDING,
        db_index=True,
    )
    # Snapshot of Paper.revision when the job was created; the drain cancels the
    # job (no model call) if the paper has moved on by pickup time.
    base_revision = models.PositiveIntegerField(default=0)
    # The endpoint request (instruction text, refine params, prior proposal …).
    request_payload = models.JSONField(default=dict, blank=True)
    # Validated, endpoint-specific result — populated on success.
    result = models.JSONField(null=True, blank=True)
    # Failure detail — set when status is failed.
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"AIJob #{self.pk} {self.kind} [{self.status}]"
