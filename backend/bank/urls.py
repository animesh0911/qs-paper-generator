"""URL routes for the bank app — mounted at ``/api/bank/`` by ``config.urls``."""
from django.urls import path

from .views import chapters, metadata

urlpatterns = [
    path("metadata/", metadata),
    path("chapters/", chapters),
]
