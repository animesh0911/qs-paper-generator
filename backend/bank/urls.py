"""URL routes for the bank app — mounted at ``/api/bank/`` by ``config.urls``."""

from django.urls import path

from .views import (
    chapters,
    generation_batch_accept,
    generation_batch_candidates,
    generation_batch_create,
    generation_batch_detail,
    ingest,
    ingest_status,
    metadata,
)

urlpatterns = [
    path("metadata/", metadata),
    path("chapters/", chapters),
    path("ingest/", ingest),
    path("ingest/<int:job_id>/", ingest_status),
    path("generation-batches/", generation_batch_create),
    path("generation-batches/<int:batch_id>/", generation_batch_detail),
    path("generation-batches/<int:batch_id>/candidates/", generation_batch_candidates),
    path("generation-batches/<int:batch_id>/accept/", generation_batch_accept),
]
