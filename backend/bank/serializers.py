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

from corpus.models import ChapterMapNode

from .generation import DIFFICULTY_TARGETS_BY_PRESET
from .models import (
    Chapter,
    GeneratedQuestionCandidate,
    GenerationBatch,
    IngestionJob,
    Question,
    SourceType,
)


class ChapterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Chapter
        fields = ["id", "slug", "name", "order"]


class ChapterTaxonomySerializer(serializers.ModelSerializer):
    """Full chapter taxonomy used by paper setup.

    Kept separate from ``ChapterSerializer`` so corpus/question nested chapter
    contracts do not change when the setup UI needs grouping metadata.
    """

    class Meta:
        model = Chapter
        fields = ["id", "slug", "name", "order", "subject_area"]


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


class GenerationBatchCreateSerializer(serializers.Serializer):
    """Validates one bulk Question-generation request."""

    chapter_slugs = serializers.ListField(
        child=serializers.SlugField(),
        min_length=1,
        allow_empty=False,
    )
    chapter_map_node_ids = serializers.ListField(
        child=serializers.CharField(allow_blank=False),
        required=False,
        default=list,
    )
    topic_names = serializers.ListField(
        child=serializers.CharField(allow_blank=False),
        required=False,
        default=list,
    )
    difficulty_preset = serializers.CharField(
        required=False,
        default="balanced",
        max_length=40,
    )
    count = serializers.IntegerField(
        required=False, default=10, min_value=1, max_value=50
    )

    def validate_chapter_slugs(self, value):
        chapters = list(Chapter.objects.filter(slug__in=value).order_by("order"))
        found = {chapter.slug for chapter in chapters}
        missing = [slug for slug in value if slug not in found]
        if missing:
            raise serializers.ValidationError(
                f"Unknown chapter slug(s): {', '.join(missing)}"
            )
        return value

    def validate_difficulty_preset(self, value):
        if value not in DIFFICULTY_TARGETS_BY_PRESET:
            raise serializers.ValidationError(f"Unknown difficulty preset: {value}")
        return value

    def validate(self, attrs):
        node_ids = attrs.get("chapter_map_node_ids") or []
        if not node_ids:
            return attrs
        chapter_slugs = attrs.get("chapter_slugs") or []
        if len(chapter_slugs) != 1:
            raise serializers.ValidationError(
                "chapter_map_node_ids require exactly one chapter_slug in the MVP."
            )
        nodes = ChapterMapNode.objects.filter(
            stable_node_id__in=node_ids,
            document__chapter__slug=chapter_slugs[0],
        )
        found = set(nodes.values_list("stable_node_id", flat=True))
        missing = [node_id for node_id in node_ids if node_id not in found]
        if missing:
            raise serializers.ValidationError(
                {"chapter_map_node_ids": f"Unknown node id(s): {', '.join(missing)}"}
            )
        return attrs


class GenerationBatchSerializer(serializers.ModelSerializer):
    """Poll shape for a bulk generation batch."""

    chapter_slugs = serializers.SerializerMethodField()
    candidate_count = serializers.SerializerMethodField()

    class Meta:
        model = GenerationBatch
        fields = [
            "id",
            "status",
            "chapter_slugs",
            "chapter_map_node_ids",
            "topic_names",
            "difficulty_preset",
            "requested_count",
            "candidate_count",
            "error",
            "ready_at",
            "accepted_at",
            "expired_at",
            "discarded_at",
            "created_at",
            "updated_at",
        ]

    def get_chapter_slugs(self, obj):
        return list(obj.chapters.order_by("order").values_list("slug", flat=True))

    def get_candidate_count(self, obj):
        return obj.candidates.count()


class GeneratedQuestionCandidateSerializer(serializers.ModelSerializer):
    """Review-list shape for valid generated Question candidates."""

    class Meta:
        model = GeneratedQuestionCandidate
        fields = [
            "id",
            "status",
            "payload",
            "grounding_manifest",
            "question_id",
            "accepted_at",
            "rejected_at",
            "created_at",
            "updated_at",
        ]


class GenerationBatchAcceptSerializer(serializers.Serializer):
    """Validates the final teacher review selection for a generation batch."""

    accepted_candidate_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
    )

    def validate_accepted_candidate_ids(self, value):
        deduped = list(dict.fromkeys(value))
        if len(deduped) != len(value):
            raise serializers.ValidationError("Duplicate candidate id in selection.")
        return deduped
