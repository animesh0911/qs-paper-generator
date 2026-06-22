"""DRF serializers for the question bank.

``QuestionSerializer`` is the only question shape exposed to clients today.
It **omits ``answer``** — used by ``papers.serializers.PaperSerializer`` so
paper-assemble and paper-detail responses never leak the answer key.

``ChapterSerializer`` is used both standalone (``GET /api/bank/chapters/``)
and nested inside the question shape.

No serializer here exposes ``answer``. Answers reach the paper owner only
through the paper-local answer document (``papers.answer_document``), which reads
``Question.answer``/``answer_source`` directly; they are never serialized into a
client-facing question/paper response.
"""

from rest_framework import serializers

from .models import Chapter, IngestionJob, Question, SourceType


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
            "id",
            "section",
            "qtype",
            "marks",
            "chapter",
            "cognitive_level",
            "text",
            "options",
        ]


class IngestionUploadSerializer(serializers.Serializer):
    """Validates a teacher's PDF-upload request (multipart/form-data).

    ``pdf`` is the source file; ``source_type`` is the caller-supplied
    provenance (one of ``SourceType``), defaulting to ``previous_year_paper`` —
    no longer hardcoded on the server. The view (not this serializer) supplies
    ``school`` and ``created_by`` from the authenticated teacher."""

    pdf = serializers.FileField()
    source_type = serializers.ChoiceField(
        choices=SourceType.choices,
        default=SourceType.PREVIOUS_YEAR_PAPER,
    )


class IngestionJobSerializer(serializers.ModelSerializer):
    """Job status shape the frontend polls — never exposes the stored PDF."""

    class Meta:
        model = IngestionJob
        fields = [
            "id",
            "status",
            "source_type",
            "source_file_name",
            "created_count",
            "skipped_count",
            "error",
            "created_at",
            "updated_at",
        ]
