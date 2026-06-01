"""URL routes for the papers app — mounted at ``/api/papers/`` by ``config.urls``."""

from django.urls import path

from .views import AssemblePaperView, PaperApproveView, PaperDetailView, PaperPdfView

urlpatterns = [
    path("assemble", AssemblePaperView.as_view(), name="assemble"),
    path("<int:pk>/", PaperDetailView.as_view(), name="paper-detail"),
    path("<int:pk>/approve/", PaperApproveView.as_view(), name="paper-approve"),
    path("<int:pk>/pdf/", PaperPdfView.as_view(), name="paper-pdf"),
]
