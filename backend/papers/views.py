from django.core.cache import cache
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .assembler import PaperAssembler
from .layout import paper_to_layout
from .models import Paper
from .pdf import render_paper_pdf
from .serializers import PaperSerializer

# Paper rows are immutable once assembled (no edit endpoint), so the rendered
# PDF can be memoised by pk indefinitely.
_PDF_CACHE_TTL = 60 * 60 * 24  # 1 day


class AssemblePaperView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        title = request.data.get("title") or "Science — Practice Paper"
        paper = PaperAssembler().assemble(request.user, title=title)
        return Response(PaperSerializer(paper).data, status=status.HTTP_201_CREATED)


class PaperDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        paper = get_object_or_404(Paper, pk=pk, created_by=request.user)
        return Response(PaperSerializer(paper).data)


class PaperPdfView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        paper = get_object_or_404(Paper, pk=pk, created_by=request.user)
        cache_key = f"paper-pdf:{paper.pk}"
        pdf = cache.get(cache_key)
        if pdf is None:
            pdf = render_paper_pdf(paper_to_layout(paper))
            cache.set(cache_key, pdf, timeout=_PDF_CACHE_TTL)
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="paper-{paper.pk}.pdf"'
        return response
