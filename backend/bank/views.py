"""Bank endpoints.

* ``GET  /api/bank/metadata/`` — canonical labels for Section / QuestionType /
  CognitiveLevel.
* ``GET  /api/bank/chapters/`` — full 13-chapter taxonomy.
* ``POST /api/bank/ingest/`` — teacher PDF upload. Persists the PDF + queues an
  ``IngestionJob`` (status ``pending``) and returns **202** with the job id. The
  Gemini extraction runs out-of-request via the ``drain_ingestion_jobs`` cron
  command — no LLM call inside the request.
* ``GET  /api/bank/ingest/{job_id}/`` — poll a job's status / result counts.
* ``POST /api/bank/generation-batches/`` — queue bulk AI Question generation.
* ``GET  /api/bank/generation-batches/{batch_id}/`` — poll generation status.
* ``GET  /api/bank/generation-batches/{batch_id}/candidates/`` — list valid
  generated candidates for teacher review.

The HTTP path is the *live* ingestion front door (teachers uploading their own
PDFs at runtime); the committed-JSON CLI path (``extract_paper`` →
``load_questions``) is the *developer* one. Both are intentional — see the
two-front-door note in CONTEXT.md ``Ingestor``.
"""

from django.db import transaction
from django.utils import timezone
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from .models import (
    ACTIVE_GENERATION_BATCH_STATUSES,
    AnswerSource,
    Chapter,
    CognitiveLevel,
    GeneratedQuestionCandidateStatus,
    GenerationBatch,
    GenerationBatchStatus,
    IngestionJob,
    ParseQuality,
    Question,
    QuestionType,
    Section,
    SourceType,
)
from .permissions import IsTeacher
from .serializers import (
    ChapterSerializer,
    GeneratedQuestionCandidateSerializer,
    GenerationBatchCreateSerializer,
    GenerationBatchSerializer,
    IngestionJobSerializer,
    IngestionUploadSerializer,
)


@api_view(["GET"])
def metadata(request):
    """Serve canonical section and question-type vocabulary."""
    return Response(
        {
            "sections": [{"code": k, "label": v} for k, v in Section.choices],
            "question_types": [
                {"code": k, "label": v} for k, v in QuestionType.choices
            ],
            "cognitive_levels": [
                {"code": k, "label": v} for k, v in CognitiveLevel.choices
            ],
        }
    )


@api_view(["GET"])
def chapters(request):
    return Response(ChapterSerializer(Chapter.objects.all(), many=True).data)


@api_view(["POST"])
@parser_classes([MultiPartParser])
@permission_classes([IsTeacher])
def ingest(request):
    """Queue a teacher's PDF for out-of-request extraction.

    Request: multipart/form-data with field ``pdf`` (file) plus optional
    ``source_type`` (one of ``SourceType``; defaults to ``previous_year_paper``).
    Persists the PDF and creates a pending ``IngestionJob`` scoped to the
    teacher's school — **no Gemini call here**. The ``drain_ingestion_jobs`` cron
    command does the extraction later.
    Response: **202** with the serialised job (``id``, ``status`` …) to poll.
    """
    serializer = IngestionUploadSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    pdf_file = serializer.validated_data["pdf"]

    job = IngestionJob.objects.create(
        school=request.user.school,
        created_by=request.user,
        pdf=pdf_file,
        source_file_name=pdf_file.name or "",
        source_type=serializer.validated_data["source_type"],
    )
    return Response(IngestionJobSerializer(job).data, status=202)


@api_view(["GET"])
@permission_classes([IsTeacher])
def ingest_status(request, job_id):
    """Return one ingestion job's status, scoped to the teacher's school.

    A teacher may only see jobs from their own school — a cross-school id is a
    404 (not 403), so the endpoint never confirms another school's job exists.
    """
    try:
        job = IngestionJob.objects.get(pk=job_id, school=request.user.school)
    except IngestionJob.DoesNotExist:
        return Response({"detail": "Not found."}, status=404)
    return Response(IngestionJobSerializer(job).data)


@api_view(["POST"])
@permission_classes([IsTeacher])
def generation_batch_create(request):
    """Queue a teacher's bulk AI Question-generation request."""
    serializer = GenerationBatchCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    GenerationBatch.expire_ready_batches()

    with transaction.atomic():
        user = type(request.user).objects.select_for_update().get(pk=request.user.pk)
        active = GenerationBatch.objects.filter(
            created_by=user,
            status__in=ACTIVE_GENERATION_BATCH_STATUSES,
        ).first()
        if active:
            return Response(
                {
                    "detail": (
                        f"Teacher already has active generation batch #{active.pk}."
                    )
                },
                status=409,
            )

        data = serializer.validated_data
        chapters_for_request = list(
            Chapter.objects.filter(slug__in=data["chapter_slugs"]).order_by("order")
        )
        batch = GenerationBatch.objects.create(
            school=user.school,
            created_by=user,
            topic_names=list(data["topic_names"]),
            difficulty_preset=data["difficulty_preset"],
            requested_count=data["count"],
        )
        batch.chapters.set(chapters_for_request)

    return Response(GenerationBatchSerializer(batch).data, status=202)


@api_view(["GET"])
@permission_classes([IsTeacher])
def generation_batch_detail(request, batch_id):
    """Return one generation batch status, scoped to the creating teacher."""
    batch = _get_owned_generation_batch(request, batch_id)
    if batch is None:
        return Response({"detail": "Not found."}, status=404)
    batch.expire_if_stale()
    return Response(GenerationBatchSerializer(batch).data)


@api_view(["GET"])
@permission_classes([IsTeacher])
def generation_batch_candidates(request, batch_id):
    """Return valid candidates for one owned generation batch."""
    batch = _get_owned_generation_batch(request, batch_id)
    if batch is None:
        return Response({"detail": "Not found."}, status=404)
    batch.expire_if_stale()
    candidates = batch.candidates.all()
    return Response(GeneratedQuestionCandidateSerializer(candidates, many=True).data)


@api_view(["POST"])
@permission_classes([IsTeacher])
def generation_batch_accept(request, batch_id):
    """Accept all ready candidates in a batch and insert them into the bank."""
    with transaction.atomic():
        batch = _get_owned_generation_batch(request, batch_id, lock=True)
        if batch is None:
            return Response({"detail": "Not found."}, status=404)
        if batch.expire_if_stale():
            return Response({"detail": "Generation batch has expired."}, status=409)
        if batch.status != GenerationBatchStatus.READY_FOR_REVIEW:
            return Response(
                {"detail": "Generation batch is not ready for review."}, status=409
            )

        candidates = list(
            batch.candidates.select_for_update().filter(
                status=GeneratedQuestionCandidateStatus.READY_FOR_REVIEW
            )
        )
        if not candidates:
            return Response(
                {"detail": "Generation batch has no candidates to accept."}, status=409
            )

        now = timezone.now()
        for candidate in candidates:
            candidate.question = _question_from_candidate(candidate, batch)
            candidate.status = GeneratedQuestionCandidateStatus.ACCEPTED
            candidate.accepted_at = now
            candidate.save(
                update_fields=["question", "status", "accepted_at", "updated_at"]
            )

        batch.status = GenerationBatchStatus.ACCEPTED
        batch.accepted_at = now
        batch.error = ""
        batch.save(update_fields=["status", "accepted_at", "error", "updated_at"])

    return Response(GenerationBatchSerializer(batch).data)


def _get_owned_generation_batch(request, batch_id, *, lock=False):
    queryset = GenerationBatch.objects.filter(
        pk=batch_id,
        created_by=request.user,
        school=request.user.school,
    ).prefetch_related("chapters")
    if lock:
        queryset = queryset.select_for_update()
    return queryset.first()


def _question_from_candidate(candidate, batch):
    payload = candidate.payload
    chapter = Chapter.objects.get(slug=payload["chapter_slug"])
    return Question.objects.create(
        school=batch.school,
        chapter=chapter,
        section=_section_for_generated_qtype(payload["qtype"]),
        qtype=payload["qtype"],
        marks=payload["marks"],
        cognitive_level=payload["cognitive_level"],
        text=payload["raw_text"],
        options=_options_from_generated_content(payload),
        content=payload["content"],
        topic_names=list(payload["topic_names"]),
        answer=payload["answer"],
        answer_source=AnswerSource.GENERATED_UNVERIFIED,
        verified=False,
        parse_quality=ParseQuality.CLEAN,
        source_type=SourceType.AI_GENERATED,
        source_name=payload.get("source", {}).get("name", ""),
    )


def _section_for_generated_qtype(qtype):
    return {
        QuestionType.MCQ: Section.A,
        QuestionType.VSA: Section.B,
        QuestionType.SA: Section.C,
        QuestionType.LA: Section.D,
    }[qtype]


def _options_from_generated_content(payload):
    if payload["qtype"] != QuestionType.MCQ:
        return []
    options = payload.get("content", {}).get("options", [])
    flattened = []
    for option in options:
        if not isinstance(option, dict):
            continue
        content = option.get("content", [])
        text = " ".join(
            item.get("text", "")
            for item in content
            if isinstance(item, dict) and isinstance(item.get("text"), str)
        ).strip()
        flattened.append({"label": option.get("label", ""), "text": text})
    return flattened
