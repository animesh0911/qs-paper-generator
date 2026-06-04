"""Django admin for the question bank — verification workflow for ingested questions."""

from django.contrib import admin, messages
from django.utils.html import format_html

from .models import AnswerSource, Chapter, Question


@admin.register(Chapter)
class ChapterAdmin(admin.ModelAdmin):
    list_display = ("order", "name", "slug")
    ordering = ("order",)


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "section",
        "qtype",
        "marks",
        "chapter",
        "cognitive_level",
        "verified",
        "answer_source",
        "has_diagram",
        "is_numerical",
        "short_text",
    )
    list_filter = (
        "verified",
        "answer_source",
        "has_diagram",
        "is_numerical",
        "section",
        "qtype",
        "chapter",
        "cognitive_level",
    )
    search_fields = ("text",)
    readonly_fields = ("source_hash", "diagram_preview")
    fields = (
        "section",
        "qtype",
        "marks",
        "chapter",
        "cognitive_level",
        "text",
        "options",
        "answer",
        "answer_source",
        "verified",
        "has_diagram",
        "is_numerical",
        "diagram",
        "diagram_preview",
        "source_hash",
    )
    actions = ["mark_verified", "mark_unverified", "approve_generated_answers"]

    # Default to showing unverified questions first in the review queue.
    ordering = ("verified", "section", "id")

    @admin.display(description="Question")
    def short_text(self, obj):
        return obj.text[:80]

    @admin.display(description="Diagram preview")
    def diagram_preview(self, obj):
        if obj.diagram:
            return format_html(
                '<img src="{}" style="max-height:200px;max-width:400px;" />',
                obj.diagram.url,
            )
        return "—"

    @admin.action(description="Mark selected questions as verified")
    def mark_verified(self, request, queryset):
        updated = queryset.update(verified=True)
        self.message_user(
            request, f"{updated} question(s) marked as verified.", messages.SUCCESS
        )

    @admin.action(description="Mark selected questions as unverified")
    def mark_unverified(self, request, queryset):
        updated = queryset.update(verified=False)
        self.message_user(
            request, f"{updated} question(s) marked as unverified.", messages.WARNING
        )

    @admin.action(description="Approve generated answers (mark as verified)")
    def approve_generated_answers(self, request, queryset):
        updated = queryset.filter(
            answer_source=AnswerSource.GENERATED_UNVERIFIED
        ).update(answer_source=AnswerSource.GENERATED_VERIFIED)
        self.message_user(
            request,
            f"{updated} generated answer(s) approved.",
            messages.SUCCESS,
        )
