from django.contrib import admin

from .models import AIJob


@admin.register(AIJob)
class AIJobAdmin(admin.ModelAdmin):
    list_display = ("id", "paper", "kind", "status", "base_revision", "created_at")
    list_filter = ("kind", "status")
    readonly_fields = ("created_at", "updated_at")
