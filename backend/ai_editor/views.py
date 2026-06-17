"""AI editor endpoints (mounted at ``/api/ai/`` by ``config.urls``).

Two synchronous surfaces answer in-request through the model seam:

* ``POST /api/ai/intent/``  — classify typed text into a route.
* ``POST /api/ai/chat/``    — read-only paper/editor answer.

Four job-creating surfaces persist a ``pending`` ``AIJob`` and return **202** —
**no model call inside the request** — to be drained out-of-request by
``drain_ai_jobs``:

* ``POST /api/ai/summarize-paper/``
* ``POST /api/ai/review-paper/``
* ``POST /api/ai/editor-edit/``
* ``POST /api/ai/editor-edit/refine/``

and one poll surface:

* ``GET  /api/ai/jobs/{jobId}/`` — status + validated result.

Every paper is scoped to its owner: a cross-user id is a 404 (never 403), so the
endpoint never confirms another teacher's paper/job exists. Only one active
(``pending``/``running``) job per **paper** is allowed at a time.
"""

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from papers.models import Paper

from . import assistant
from .models import ACTIVE_AI_JOB_STATUSES, AIJob, AIJobKind
from .serializers import AIJobSerializer, JobRequestSerializer, TypedTextSerializer


def _get_owned_paper(request, paper_id, *, lock=False):
    """Fetch a draft-or-any paper owned by the caller, or 404.

    ``lock`` takes a ``select_for_update`` row lock so the one-active-job guard
    cannot race two concurrent create requests for the same paper.
    """
    queryset = Paper.objects.all()
    if lock:
        queryset = queryset.select_for_update()
    return get_object_or_404(queryset, pk=paper_id, created_by=request.user)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def intent(request):
    """Classify typed text into an editor route (sync, live model call)."""
    serializer = TypedTextSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    paper = _get_owned_paper(request, serializer.validated_data["paperId"])
    result = assistant.classify_intent(
        serializer.validated_data["text"], paper_title=paper.title
    )
    return Response(result)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def chat(request):
    """Answer a read-only paper/editor question (sync, live model call)."""
    serializer = TypedTextSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    paper = _get_owned_paper(request, serializer.validated_data["paperId"])
    message = assistant.answer_chat(
        serializer.validated_data["text"], paper_title=paper.title
    )
    return Response({"status": "chat", "message": message})


def _create_job(request, kind):
    """Persist a pending AIJob for ``kind`` and return 202, or 409 if busy.

    The paper is row-locked while we check for an existing non-terminal job, so
    two concurrent creates cannot both pass the one-active-job-per-paper guard
    and double-bill the paid drain (Rule 13).
    """
    serializer = JobRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    with transaction.atomic():
        paper = _get_owned_paper(
            request, serializer.validated_data["paperId"], lock=True
        )
        active = paper.ai_jobs.filter(status__in=ACTIVE_AI_JOB_STATUSES).first()
        if active is not None:
            return Response(
                {
                    "detail": "This paper already has an AI job in progress.",
                    "jobId": active.pk,
                },
                status=409,
            )
        job = AIJob.objects.create(
            paper=paper,
            created_by=request.user,
            kind=kind,
            base_revision=paper.revision,
            request_payload={"instruction": serializer.validated_data["instruction"]},
        )
    return Response(AIJobSerializer(job).data, status=202)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def summarize_paper(request):
    return _create_job(request, AIJobKind.SUMMARY)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def review_paper(request):
    return _create_job(request, AIJobKind.REVIEW)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def editor_edit(request):
    return _create_job(request, AIJobKind.EDITOR_EDIT)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def editor_edit_refine(request):
    return _create_job(request, AIJobKind.REFINE)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def job_status(request, job_id):
    """Poll one job's status/result, scoped to the paper's owner."""
    job = get_object_or_404(AIJob, pk=job_id, paper__created_by=request.user)
    return Response(AIJobSerializer(job).data)
