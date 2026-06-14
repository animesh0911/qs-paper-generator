"""Django application configuration for the developer-populated NCERT corpus."""

from django.apps import AppConfig


class CorpusConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "corpus"
