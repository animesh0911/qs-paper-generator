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
