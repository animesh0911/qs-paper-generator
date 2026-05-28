"""DRF serializers for the question bank.

``QuestionSerializer`` is the only question shape exposed to clients today.
It **omits ``answer``** — used by ``papers.serializers.PaperSerializer`` so
paper-assemble and paper-detail responses never leak the answer key.

``ChapterSerializer`` is used both standalone (``GET /api/bank/chapters/``)
and nested inside the question shape.

An answer-revealing serializer + the gating rule that decides who may use it
will land together when the first answer-key endpoint is built (Slice 9).
"""
from rest_framework import serializers

from .models import Chapter, Question


class ChapterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Chapter
        fields = ["id", "slug", "name", "order"]


class QuestionSerializer(serializers.ModelSerializer):
    """Default question shape exposed to clients. Omits ``answer`` by design."""

    chapter = ChapterSerializer(read_only=True)

    class Meta:
        model = Question
        fields = [
            "id", "section", "qtype", "marks",
            "chapter", "cognitive_level",
            "text", "options",
        ]
