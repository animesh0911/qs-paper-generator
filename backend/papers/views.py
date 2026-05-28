from django.core.cache import cache
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .assembler import PaperAssembler
from .layout import paper_to_layout
from .models import Paper
from .pdf import render_paper_pdf
from .selection import DEFAULT_PROFILE, PROFILE_NAMES
from .serializers import PaperSerializer

# Paper rows are immutable once assembled (no edit endpoint), so the rendered
# PDF can be memoised by pk indefinitely.
_PDF_CACHE_TTL = 60 * 60 * 24  # 1 day


class AssemblePaperView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data or {}
        title = data.get("title") or "Science — Practice Paper"
        preset = data.get("preset") or "board"
        chapter_slugs = data.get("chapter_slugs") or []
        weights = data.get("weights") or {}
        difficulty = data.get("difficulty") or DEFAULT_PROFILE

        if not isinstance(chapter_slugs, list) or not all(
            isinstance(s, str) for s in chapter_slugs
        ):
            raise ValidationError({"chapter_slugs": "must be a list of slug strings"})
        if not isinstance(weights, dict):
            raise ValidationError({"weights": "must be an object mapping slug -> number"})
        for k, v in weights.items():
            if not isinstance(k, str) or not isinstance(v, (int, float)):
                raise ValidationError(
                    {"weights": "keys must be slug strings, values numeric"}
                )
        if difficulty not in PROFILE_NAMES:
            raise ValidationError(
                {"difficulty": f"must be one of {PROFILE_NAMES}"}
            )

        paper = PaperAssembler().assemble(
            request.user,
            title=title,
            preset=preset,
            chapter_slugs=chapter_slugs,
            weights=weights,
            difficulty=difficulty,
        )
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
