from rest_framework import serializers

from bank.serializers import QuestionSerializer

from .blueprint import PRESET_NAMES
from .models import Paper, PaperQuestion
from .selection import DEFAULT_PROFILE, PROFILE_NAMES


class AssembleRequestSerializer(serializers.Serializer):
    """Validate the payload accepted by AssemblePaperView.

    Owns the input contract for paper assembly. The view hands its
    ``validated_data`` straight to ``PaperAssembler.assemble(**...)``, so
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
        choices=PROFILE_NAMES, required=False, default=DEFAULT_PROFILE
    )

    def validate_title(self, value: str) -> str:
        # Empty title means "use the assembler's default" — strip and let the
        # caller fall back rather than persisting an empty string.
        return value.strip()


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
            "id", "title", "total_marks",
            "report",
            "created_at", "items",
        ]
