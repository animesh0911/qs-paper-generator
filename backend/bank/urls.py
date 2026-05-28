from django.urls import path

from .views import metadata

urlpatterns = [
    path("metadata/", metadata),
]
