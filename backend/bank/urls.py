"""URL routes for the bank app — mounted at ``/api/bank/`` by ``config.urls``."""

from django.urls import path

from .views import chapters, ingest, ingest_marking_scheme, metadata

urlpatterns = [
    path("metadata/", metadata),
    path("chapters/", chapters),
    path("ingest/", ingest),
    path("ingest-marking-scheme/", ingest_marking_scheme),
]
