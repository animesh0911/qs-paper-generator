"""DRF serializers for the question bank.

``QuestionSerializer`` is the only question shape exposed to clients today.
It **omits ``answer``** — used by ``papers.serializers.PaperSerializer`` so
paper-assemble and paper-detail responses never leak the answer key.

``ChapterSerializer`` is used both standalone (``GET /api/bank/chapters/``)
and nested inside the question shape.

``AnswerKeySerializer`` is the only shape that reveals ``answer``. It exists
solely to build the marking-scheme PDF and must never be nested in a
client-facing question/paper response — answers stay gated behind the
owner-scoped answer-key endpoint (``papers.views.PaperAnswerKeyPdfView``).
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


class AnswerKeySerializer(serializers.ModelSerializer):
    """Answer-revealing question shape — the one place ``answer`` is exposed.

    Used only by the answer-key endpoint to assemble the marking scheme. The
    access rule (paper owner only) lives at the view, which also uses
    ``answer_source`` to suppress unverified generated answers. Carries only
    those fields — nothing renderable to clients.
    """

    class Meta:
        model = Question
        fields = ["id", "marks", "answer", "answer_source"]


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
