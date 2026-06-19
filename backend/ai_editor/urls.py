"""URL routes for the AI editor app — mounted at ``/api/ai/`` by ``config.urls``."""

from django.urls import path

from .views import (
    chat,
    editor_edit,
    editor_edit_refine,
    intent,
    job_status,
    review_paper,
    summarize_paper,
)

urlpatterns = [
    path("intent/", intent),
    path("chat/", chat),
    path("summarize-paper/", summarize_paper),
    path("review-paper/", review_paper),
    path("editor-edit/", editor_edit),
    path("editor-edit/refine/", editor_edit_refine),
    path("jobs/<int:job_id>/", job_status),
]
