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

from .citation_support import review_candidate_citation_support
from .generation import DIFFICULTY_TARGETS_BY_PRESET
from .models import (
    AnswerGenerationJob,
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


class BankQuestionSerializer(serializers.ModelSerializer):
    """Question shape for the browsable bank view.

    Extends the default shape with provenance and quality metadata a teacher
    needs to scan the bank (source, parse quality, verification, created_at).
    Still omits ``answer`` — answers only reach the paper-local answer document.
    """

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
            "content",
            "options",
            "primary_form",
            "topic_names",
            "parse_quality",
            "review_flags",
            "verified",
            "source_type",
            "source_name",
            "source_file_name",
            "created_at",
        ]


MAX_UPLOAD_PDF_BYTES = 25 * 1024 * 1024  # Mirrors the dropzone's "up to 25 MB".


class IngestionUploadSerializer(serializers.Serializer):
    """Validates a teacher's PDF-upload request (multipart/form-data).

    ``pdf`` is the source file; ``source_type`` is the caller-supplied
    provenance (one of ``SourceType``), defaulting to ``previous_year_paper`` —
    no longer hardcoded on the server. The view (not this serializer) supplies
    ``school`` and ``created_by`` from the authenticated teacher.

    The size/magic-byte checks reject a bad file at upload time with an
    actionable message, instead of queueing a job the drain worker can only
    fail minutes later."""

    pdf = serializers.FileField()
    source_type = serializers.ChoiceField(
        choices=SourceType.choices,
        default=SourceType.PREVIOUS_YEAR_PAPER,
    )

    def validate_pdf(self, value):
        if value.size > MAX_UPLOAD_PDF_BYTES:
            raise serializers.ValidationError(
                "This file is larger than 25 MB. Compress the PDF or split the "
                "paper into smaller files, then try again."
            )
        head = value.read(5)
        value.seek(0)
        if head != b"%PDF-":
            raise serializers.ValidationError(
                "This file is not a PDF. Export or scan the paper as a PDF, "
                "then try again."
            )
        return value


class IngestionJobSerializer(serializers.ModelSerializer):
    """Job status shape the frontend polls — never exposes the stored PDF."""

    class Meta:
        model = IngestionJob
        fields = [
            "id",
            "status",
            "source_type",
            "source_file_name",
            "total_pages",
            "pages_done",
            "created_count",
            "skipped_count",
            "error",
            "created_at",
            "updated_at",
        ]


class AnswerGenerationJobSerializer(serializers.ModelSerializer):
    """Poll shape for optional answer generation from one upload."""

    class Meta:
        model = AnswerGenerationJob
        fields = [
            "id",
            "ingestion_job_id",
            "status",
            "total_count",
            "generated_count",
            "skipped_count",
            "error",
            "created_at",
            "updated_at",
        ]


class GeneratedAnswerSerializer(serializers.ModelSerializer):
    """Generated answer shape keyed to an extracted question."""

    question_id = serializers.IntegerField(source="id")

    class Meta:
        model = Question
        fields = ["question_id", "answer", "answer_source"]


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
        # The list view annotates the count so 20 polled batches don't issue 20
        # extra COUNT queries; single-batch serialization falls back to a query.
        annotated = getattr(obj, "candidate_count_annotation", None)
        return obj.candidates.count() if annotated is None else annotated


class GeneratedQuestionCandidateSerializer(serializers.ModelSerializer):
    """Review-list shape for valid generated Question candidates."""

    support_review = serializers.SerializerMethodField()

    class Meta:
        model = GeneratedQuestionCandidate
        fields = [
            "id",
            "status",
            "payload",
            "grounding_manifest",
            "support_review",
            "question_id",
            "accepted_at",
            "rejected_at",
            "created_at",
            "updated_at",
        ]

    def get_support_review(self, obj):
        """Deterministic citation-support screen (``bank.citation_support``).

        Computed at serialization time so no migration/backfill is needed: it
        checks whether the cited NCERT excerpts lexically support the generated
        question and answer, and flags formula/diagram-shaped prompts. ``None``
        for ungrounded batches (no excerpts to check against). This is a
        review aid, not a proof — the teacher still owns acceptance.
        """
        manifest = obj.grounding_manifest or {}
        if not isinstance(manifest, dict) or not manifest.get("excerpts"):
            return None
        review = review_candidate_citation_support(obj.payload or {}, manifest)
        return {
            "supported": review.supported,
            "question_supported": review.question_supported,
            "answer_supported": review.answer_supported,
            "issues": [
                {"field": issue.field, "code": issue.code, "detail": issue.detail}
                for issue in review.issues
            ],
        }


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
