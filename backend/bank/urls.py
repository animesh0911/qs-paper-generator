"""URL routes for the bank app — mounted at ``/api/bank/`` by ``config.urls``."""

from django.urls import path

from .views import chapters, ingest, ingest_status, metadata

urlpatterns = [
    path("metadata/", metadata),
    path("chapters/", chapters),
    path("ingest/", ingest),
    path("ingest/<int:job_id>/", ingest_status),
]
