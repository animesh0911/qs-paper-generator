"""Read-only bank endpoints.

Two endpoints, both consumed by the frontend at startup:

* ``GET /api/bank/metadata/`` — canonical labels for ``Section``,
  ``QuestionType``, ``CognitiveLevel``. The frontend uses this to render
  section titles and difficulty options without hardcoding strings.
* ``GET /api/bank/chapters/`` — full 13-chapter taxonomy. Drives the
  chapter checklist in the coverage form.
"""
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import Chapter, CognitiveLevel, QuestionType, Section
from .serializers import ChapterSerializer


@api_view(["GET"])
def metadata(request):
    """Serve canonical section and question-type vocabulary.

    Single source of truth so frontend and PDF renderer don't hardcode labels.
    """
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
