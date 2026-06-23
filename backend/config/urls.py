from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def healthz(_request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz", healthz),
    path("api/ai/", include("ai_editor.urls")),
    path("api/auth/", include("accounts.urls")),
    path("api/bank/", include("bank.urls")),
    path("api/corpus/", include("corpus.urls")),
    path("api/papers/", include("papers.urls")),
]

# Serve uploaded assets (cropped diagrams) in development so the editor-draft
# asset URLs resolve locally. In production media is served by the storage
# backend (e.g. signed S3/CDN URLs from ``default_storage.url``), not Django.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
