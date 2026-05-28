"""DRF serializers for the question bank.

Two key adapters:

* ``QuestionSerializer`` — the default question shape; **omits ``answer``**.
  Used by ``papers.serializers.PaperSerializer`` so paper-assemble and
  paper-detail responses never leak the answer key.
* ``QuestionWithAnswerSerializer`` — same shape plus ``answer``. Only mount
  it behind ``bank.policy.answer_visible``-gated endpoints.

``ChapterSerializer`` is used both standalone (``GET /api/bank/chapters/``)
and nested inside the question shapes.
"""
from rest_framework import serializers

from .models import Chapter, Question


class ChapterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Chapter
        fields = ["id", "slug", "name", "order"]


class QuestionSerializer(serializers.ModelSerializer):
    """Default question shape exposed to clients.

    `answer` is deliberately omitted so paper-assemble/detail responses do not
    leak the answer key. Use ``QuestionWithAnswerSerializer`` for explicit
    answer-key endpoints once they exist.
    """

    chapter = ChapterSerializer(read_only=True)

    class Meta:
        model = Question
        fields = [
            "id", "section", "qtype", "marks",
            "chapter", "cognitive_level",
            "text", "options",
        ]


class QuestionWithAnswerSerializer(serializers.ModelSerializer):
    """Include answer field. Gate the endpoint on bank.policy.answer_visible()."""

    chapter = ChapterSerializer(read_only=True)

    class Meta:
        model = Question
        fields = [
            "id", "section", "qtype", "marks",
            "chapter", "cognitive_level",
            "text", "options", "answer",
        ]
