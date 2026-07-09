"""Django bootstrap for standalone eval scripts.

Eval entrypoints run as ``python -m evals.run ...`` inside the web container
(host Python cannot run Django 5.1). They import ORM-backed production code
(Chapter enum in the extraction schema, Question rows, pgvector corpus), so
Django must be configured before any ``bank``/``corpus`` import.

Call :func:`ensure_django` first thing in every ``__main__`` path. Importing
``evals.scenarios.*`` without it fails loudly with Django's own
ImproperlyConfigured — never silently.
"""

from __future__ import annotations

import os

_DEFAULT_SETTINGS = "config.settings"


def ensure_django() -> None:
    """Idempotently configure Django for standalone execution."""
    import django
    from django.apps import apps

    if apps.ready:
        return
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", _DEFAULT_SETTINGS)
    django.setup()
