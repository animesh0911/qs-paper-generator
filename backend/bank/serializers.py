from rest_framework import serializers

from .models import Question


class QuestionSerializer(serializers.ModelSerializer):
    """Default question shape exposed to clients.

    `answer` is deliberately omitted so paper-assemble/detail responses do not
    leak the answer key. Use ``QuestionWithAnswerSerializer`` for explicit
    answer-key endpoints once they exist.
    """

    class Meta:
        model = Question
        fields = ["id", "section", "qtype", "marks", "text", "options"]


class QuestionWithAnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = ["id", "section", "qtype", "marks", "text", "options", "answer"]
