"""Django admin registration for the question bank.

Light-touch admin so teachers and operators can spot-check seeded data and
diagnose unfilled-slot reports by filtering questions on chapter and
cognitive level.
"""
from django.contrib import admin

from .models import Chapter, Question


@admin.register(Chapter)
class ChapterAdmin(admin.ModelAdmin):
    list_display = ("order", "name", "slug")
    ordering = ("order",)


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("id", "section", "qtype", "marks", "chapter", "cognitive_level", "short_text")
    list_filter = ("section", "qtype", "chapter", "cognitive_level")
    search_fields = ("text",)

    @admin.display(description="Question")
    def short_text(self, obj):
        return obj.text[:80]
