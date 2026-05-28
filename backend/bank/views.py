from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import QuestionType, Section


@api_view(["GET"])
def metadata(request):
    """Serve canonical section and question-type vocabulary.

    Single source of truth so frontend and PDF renderer don't hardcode labels.
    """
    return Response(
        {
            "sections": [{"code": k, "label": v} for k, v in Section.choices],
            "question_types": [{"code": k, "label": v} for k, v in QuestionType.choices],
        }
    )
