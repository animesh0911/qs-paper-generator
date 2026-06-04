"""DRF serializers for the paper-assembly API.

Two roles:

* ``AssembleRequestSerializer`` — input contract for
  ``POST /api/papers/assemble``. Owns every constraint on assemble input
  (preset whitelist, difficulty whitelist, slug list shape, weights as
  ``{slug: float >= 0}``). New input fields accrete here, not in the view.
* ``PaperSerializer`` / ``PaperQuestionSerializer`` — output shape returned
  by assemble and detail endpoints. ``PaperQuestionSerializer`` nests
  ``QuestionSerializer``, which omits the answer key.
"""

from rest_framework import serializers

from bank.serializers import QuestionSerializer

from .models import Paper, PaperFormat, PaperQuestion
from .picker import DEFAULT_DIFFICULTY, DIFFICULTY_NAMES
from .template import PRESET_NAMES


class AssembleRequestSerializer(serializers.Serializer):
    """Validate the payload accepted by AssemblePaperView.

    Owns the input contract for paper assembly. The view hands its
    ``validated_data`` straight to ``PaperBuilder.assemble(**...)``, so
    field names here must stay in lockstep with that signature.
    """

    title = serializers.CharField(
        required=False, allow_blank=True, max_length=255, default=""
    )
    preset = serializers.ChoiceField(
        choices=PRESET_NAMES, required=False, default="board"
    )
    chapter_slugs = serializers.ListField(
        child=serializers.SlugField(),
        required=False,
        default=list,
    )
    weights = serializers.DictField(
        child=serializers.FloatField(min_value=0),
        required=False,
        default=dict,
    )
    difficulty = serializers.ChoiceField(
        choices=DIFFICULTY_NAMES, required=False, default=DEFAULT_DIFFICULTY
    )
    # Questions the teacher wants reused despite freshness (Slice 10). Exempts
    # them from the usage penalty so a deliberately-repeated question competes
    # as if unused.
    reuse_question_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        default=list,
    )
    format_id = serializers.CharField(required=False, allow_null=True, default=None)

    def validate_title(self, value: str) -> str:
        # Empty title means "use the assembler's default" — strip and let the
        # caller fall back rather than persisting an empty string.
        return value.strip()

    def validate(self, data):
        # Reject unknown formats at the API boundary so the caller gets a 4xx,
        # not the 500 the builder's .get() would raise. The preset derived from
        # the format is owned by PaperBuilder, not duplicated here.
        format_id = data.get("format_id")
        if (
            format_id
            and not PaperFormat.objects.filter(
                format_id=format_id, is_active=True
            ).exists()
        ):
            raise serializers.ValidationError(
                {"format_id": f"Unsupported format_id: {format_id!r}"}
            )
        return data


class PaperQuestionSerializer(serializers.ModelSerializer):
    question = QuestionSerializer(read_only=True)

    class Meta:
        model = PaperQuestion
        fields = ["order", "section", "question"]


class PaperSerializer(serializers.ModelSerializer):
    items = PaperQuestionSerializer(many=True, read_only=True)

    class Meta:
        model = Paper
        fields = [
            "id",
            "title",
            "total_marks",
            "status",
            "report",
            "created_at",
            "items",
        ]
