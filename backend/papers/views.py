"""HTTP views for paper assembly, detail, edit, approve, and PDF download.

``AssemblePaperView`` — thin: validate, call PaperBuilder, return document.
``PaperDetailView`` — GET returns stored document; PATCH overwrites it (drafts only).
``PaperApproveView`` — POST locks paper to APPROVED.
``PaperPdfView`` — GET renders PDF from paper.document (cached 24h after approve).
``PaperAnswerKeyPdfView`` — GET renders the separate marking-scheme PDF; the
only path that reveals answers, gated to the paper owner.

Domain rules live in ``papers.builder`` and ``papers.picker``.
"""

from django.conf import settings
from django.core.cache import cache
from django.db.models import F
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from bank.models import AnswerSource, Question
from bank.serializers import AnswerKeySerializer

from .builder import PaperBuilder
from .models import Paper, PaperFormat, PaperStatus
from .pdf import render_answer_key_pdf, render_paper_pdf
from .serializers import AssembleRequestSerializer, PaperSerializer

_PDF_CACHE_TTL = 60 * 60 * 24  # 1 day
_SCHEMA_VERSION = "paper_document.v1"


class PaperFormatsView(APIView):
    """Return available paper formats for the frontend format selector."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        formats = list(
            PaperFormat.objects.filter(is_active=True).values("format_id", "name")
        )
        return Response(formats)


class AssemblePaperView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        req = AssembleRequestSerializer(data=request.data or {})
        req.is_valid(raise_exception=True)
        params = dict(req.validated_data)
        if not params.get("title"):
            params.pop("title", None)
        result = PaperBuilder().assemble(request.user, **params)
        return Response(result.document, status=status.HTTP_201_CREATED)


class PaperDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        paper = get_object_or_404(Paper, pk=pk, created_by=request.user)
        if paper.document is not None:
            return Response(paper.document)
        return Response(PaperSerializer(paper).data)

    def patch(self, request, pk):
        paper = get_object_or_404(Paper, pk=pk, created_by=request.user)
        if paper.status != PaperStatus.DRAFT:
            return Response(
                {"error": "Only draft papers can be edited."},
                status=status.HTTP_409_CONFLICT,
            )
        document = request.data.get("document")
        if (
            not isinstance(document, dict)
            or document.get("schemaVersion") != _SCHEMA_VERSION
        ):
            return Response(
                {"error": f"document.schemaVersion must be '{_SCHEMA_VERSION}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        paper.document = document
        # Bump the revision so a queued AI job (#31) whose base_revision was
        # taken before this edit is cancelled by the drain instead of spending
        # paid tokens on a now-stale proposal (Rule 13).
        paper.revision = F("revision") + 1
        paper.save(update_fields=["document", "revision"])
        paper.refresh_from_db(fields=["revision"])
        return Response({"paperId": f"paper_{paper.pk}", "status": paper.status})


class PaperApproveView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        paper = get_object_or_404(Paper, pk=pk, created_by=request.user)
        if paper.status != PaperStatus.DRAFT:
            return Response(
                {"error": "Paper is already approved."},
                status=status.HTTP_409_CONFLICT,
            )
        paper.approve()
        return Response({"paperId": f"paper_{paper.pk}", "status": paper.status})


class PaperPdfView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        paper = get_object_or_404(Paper, pk=pk, created_by=request.user)
        document = paper.document or {}
        print_url = _paper_print_url(request.user, paper.pk)
        if paper.status == PaperStatus.APPROVED:
            cache_key = f"paper-pdf:{paper.pk}"
            pdf = cache.get(cache_key)
            if pdf is None:
                pdf = render_paper_pdf(document, print_url=print_url)
                cache.set(cache_key, pdf, timeout=_PDF_CACHE_TTL)
        else:
            pdf = render_paper_pdf(document, print_url=print_url)
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="paper-{paper.pk}.pdf"'
        return response


class PaperAnswerKeyPdfView(APIView):
    """Render the marking-scheme PDF — the one endpoint that reveals answers.

    Owner-scoped (``created_by=request.user``) so answers never reach another
    teacher's request. Answers are read through ``AnswerKeySerializer`` and
    joined to the canonical document by question id; the document itself still
    carries no answers. Cached 24h once the paper is approved, matching the
    exam PDF.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        paper = get_object_or_404(Paper, pk=pk, created_by=request.user)
        document = paper.document or {}
        if paper.status == PaperStatus.APPROVED:
            cache_key = f"paper-answer-key-pdf:{paper.pk}"
            pdf = cache.get(cache_key)
            if pdf is None:
                pdf = render_answer_key_pdf(document, self._answers_by_id(paper))
                cache.set(cache_key, pdf, timeout=_PDF_CACHE_TTL)
        else:
            pdf = render_answer_key_pdf(document, self._answers_by_id(paper))
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = (
            f'inline; filename="paper-{paper.pk}-answer-key.pdf"'
        )
        return response

    def _answers_by_id(self, paper: Paper) -> dict[str, str]:
        """Map contract question id (``"q_{pk}"``) to answer for selected slots.

        ``generated_unverified`` answers are suppressed — they fall through to
        the ``(no answer on file)`` placeholder until a teacher approves them.
        """
        pks = paper._referenced_question_ids()
        rows = AnswerKeySerializer(Question.objects.filter(pk__in=pks), many=True).data
        return {
            f"q_{row['id']}": row["answer"]
            for row in rows
            if row["answer_source"] != AnswerSource.GENERATED_UNVERIFIED
        }


def _paper_print_url(user, paper_pk: int) -> str | None:
    base_url = settings.PAPER_PRINT_BASE_URL.rstrip("/")
    if not base_url:
        return None
    token, _ = Token.objects.get_or_create(user=user)
    return f"{base_url}/editor/{paper_pk}/print?token={token.key}"
