"""Bank endpoints.

* ``GET  /api/bank/metadata/`` — canonical labels for Section / QuestionType / CognitiveLevel.
* ``GET  /api/bank/chapters/`` — full 13-chapter taxonomy.
* ``POST /api/bank/ingest/``   — admin-only PDF upload; parses + auto-tags + stores questions.
"""
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from .models import Chapter, CognitiveLevel, Question, QuestionType, Section
from .serializers import ChapterSerializer


@api_view(["GET"])
def metadata(request):
    """Serve canonical section and question-type vocabulary."""
    return Response(
        {
            "sections": [{"code": k, "label": v} for k, v in Section.choices],
            "question_types": [{"code": k, "label": v} for k, v in QuestionType.choices],
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
    from .ingestor import extract_text, segment_questions, strip_hindi, tag_with_claude

    pdf_file = request.FILES.get("pdf")
    if pdf_file is None:
        return Response({"detail": "Field 'pdf' is required."}, status=400)

    pdf_bytes = pdf_file.read()
    raw_text = extract_text(pdf_bytes)
    clean_text = strip_hindi(raw_text)
    raw_questions = segment_questions(clean_text)

    if not raw_questions:
        return Response({"created": 0})

    all_chapters = list(Chapter.objects.all())
    tagged = tag_with_claude(raw_questions, all_chapters)

    chapter_by_slug = {c.slug: c for c in all_chapters}
    to_create = []
    for q in tagged:
        chapter = chapter_by_slug.get(q.get("chapter_slug"))
        to_create.append(
            Question(
                chapter=chapter,
                section=q["section"],
                qtype=q["qtype"],
                marks=q["marks"],
                cognitive_level=q.get("cognitive_level", CognitiveLevel.REMEMBER),
                text=q["text"],
                options=q.get("options", []),
                answer="",
                verified=False,
            )
        )

    created = Question.objects.bulk_create(to_create)
    return Response({"created": len(created)})
