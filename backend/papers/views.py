"""HTTP views for paper assembly, detail, and PDF download.

``AssemblePaperView`` is intentionally thin: validate via
``AssembleRequestSerializer``, call ``PaperAssembler``, serialize. Domain
rules live in ``papers.assembler`` and ``papers.selection``.

``PaperPdfView`` memoises the rendered PDF for 24h keyed on paper id —
papers are immutable once assembled, so the cache is safe.
"""
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
from .serializers import AssembleRequestSerializer, PaperSerializer

# Paper rows are immutable once assembled (no edit endpoint), so the rendered
# PDF can be memoised by pk indefinitely.
_PDF_CACHE_TTL = 60 * 60 * 24  # 1 day


class AssemblePaperView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        req = AssembleRequestSerializer(data=request.data or {})
        req.is_valid(raise_exception=True)
        params = dict(req.validated_data)
        # Title defaults are owned by the assembler, not the validator, so an
        # empty string here means "fall back".
        if not params.get("title"):
            params.pop("title", None)
        paper = PaperAssembler().assemble(request.user, **params)
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
