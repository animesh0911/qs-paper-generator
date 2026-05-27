from django.contrib import admin

from .models import Question


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("id", "section", "qtype", "marks", "short_text")
    list_filter = ("section", "qtype")
    search_fields = ("text",)

    @admin.display(description="Question")
    def short_text(self, obj):
        return obj.text[:80]
