from rest_framework import serializers

from bank.serializers import QuestionSerializer

from .models import Paper, PaperQuestion


class PaperQuestionSerializer(serializers.ModelSerializer):
    question = QuestionSerializer(read_only=True)

    class Meta:
        model = PaperQuestion
        fields = ["order", "section", "question"]


class PaperSerializer(serializers.ModelSerializer):
    items = PaperQuestionSerializer(many=True, read_only=True)

    class Meta:
        model = Paper
        fields = ["id", "title", "total_marks", "created_at", "items"]
