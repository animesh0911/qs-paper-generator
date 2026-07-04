"""URL routes for the bank app — mounted at ``/api/bank/`` by ``config.urls``."""

from django.urls import path

from .views import (
    chapters,
    generation_batch_accept,
    generation_batch_candidates,
    generation_batch_detail,
    generation_batch_discard,
    generation_batches,
    ingest,
    ingest_answers,
    ingest_questions,
    ingest_status,
    metadata,
    question_sources,
    questions,
    sources,
)

urlpatterns = [
    path("metadata/", metadata),
    path("question-sources/", question_sources),
    path("chapters/", chapters),
    path("sources/", sources),
    path("questions/", questions),
    path("ingest/", ingest),
    path("ingest/<int:job_id>/", ingest_status),
    path("ingest/<int:job_id>/questions/", ingest_questions),
    path("ingest/<int:job_id>/answers/", ingest_answers),
    path("generation-batches/", generation_batches),
    path("generation-batches/<int:batch_id>/", generation_batch_detail),
    path("generation-batches/<int:batch_id>/candidates/", generation_batch_candidates),
    path("generation-batches/<int:batch_id>/accept/", generation_batch_accept),
    path("generation-batches/<int:batch_id>/discard/", generation_batch_discard),
]
