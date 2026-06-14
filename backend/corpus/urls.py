"""URL routes for corpus chapter-map inspection."""

from django.urls import path

from .views import chapter_map, chapter_map_node_details

urlpatterns = [
    path("documents/<int:document_id>/chapter-map/", chapter_map),
    path(
        "documents/<int:document_id>/chapter-map/nodes/<str:stable_node_id>/",
        chapter_map_node_details,
    ),
]
