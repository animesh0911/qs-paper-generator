from django.urls import path

from .views import chapters, metadata

urlpatterns = [
    path("metadata/", metadata),
    path("chapters/", chapters),
]
