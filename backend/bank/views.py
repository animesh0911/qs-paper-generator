"""Bank endpoints.

* ``GET  /api/bank/metadata/`` — canonical labels for Section / QuestionType /
  CognitiveLevel.
* ``GET  /api/bank/chapters/`` — full 13-chapter taxonomy.
* ``POST /api/bank/ingest/`` — teacher PDF upload. Persists the PDF + queues an
  ``IngestionJob`` (status ``pending``) and returns **202** with the job id. The
  Gemini extraction runs out-of-request via the ``drain_ingestion_jobs`` cron
  command — no LLM call inside the request.
* ``GET  /api/bank/ingest/{job_id}/`` — poll a job's status / result counts.

The HTTP path is the *live* ingestion front door (teachers uploading their own
PDFs at runtime); the committed-JSON CLI path (``extract_paper`` →
``load_questions``) is the *developer* one. Both are intentional — see the
two-front-door note in CONTEXT.md ``Ingestor``.
"""

from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from .models import Chapter, CognitiveLevel, IngestionJob, QuestionType, Section
from .permissions import IsTeacher
from .serializers import (
    ChapterSerializer,
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
