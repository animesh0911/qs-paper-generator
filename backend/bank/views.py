"""Bank endpoints.

* ``GET  /api/bank/metadata/`` — canonical labels for Section / QuestionType /
  CognitiveLevel.
* ``GET  /api/bank/chapters/`` — full 13-chapter taxonomy.
* ``POST /api/bank/ingest/`` — admin-only PDF upload; parses + auto-tags +
  stores questions.
* ``POST /api/bank/ingest-marking-scheme/`` — admin-only marking-scheme PDF
  upload; matches answers.
"""

from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from .models import Chapter, CognitiveLevel, QuestionType, Section
from .serializers import ChapterSerializer


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
@permission_classes([IsAdminUser])
def ingest(request):
    """Parse a CBSE past-paper PDF and store questions as unverified.

    Request: multipart/form-data with field ``pdf`` (file).
    Response: ``{"created": N}`` — count of Question rows bulk-created.
    """
    from .ingestor import Ingestor

    pdf_file = request.FILES.get("pdf")
    if pdf_file is None:
        return Response({"detail": "Field 'pdf' is required."}, status=400)

    result = Ingestor().ingest(pdf_file.read())
    return Response(
        {"created": result.created, "skipped_duplicates": result.skipped_duplicates}
    )


@api_view(["POST"])
@parser_classes([MultiPartParser])
@permission_classes([IsAdminUser])
def ingest_marking_scheme(request):
    """Parse a CBSE marking-scheme PDF and update Question.answer for matched rows.

    Request: multipart/form-data with field ``pdf`` (file).
    Response: ``{"updated": N}`` — count of Question rows with answers filled in.
    """
    from .ingestor import Ingestor

    pdf_file = request.FILES.get("pdf")
    if pdf_file is None:
        return Response({"detail": "Field 'pdf' is required."}, status=400)

    updated = Ingestor().apply_answers(pdf_file.read())
    return Response({"updated": updated})
