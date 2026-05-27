from django.urls import path

from .views import AssemblePaperView, PaperDetailView, PaperPdfView

urlpatterns = [
    path("assemble", AssemblePaperView.as_view(), name="assemble"),
    path("<int:pk>", PaperDetailView.as_view(), name="paper-detail"),
    path("<int:pk>/pdf", PaperPdfView.as_view(), name="paper-pdf"),
]
