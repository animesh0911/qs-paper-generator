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
from django.core.files.storage import default_storage
from django.db.models import F
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .answer_document import (
    build_answer_document,
    printable_answers_by_slot,
    validate_answer_document,
)
from .assets import strip_resolved_asset_urls, with_resolved_asset_urls
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


class PaperEditorDraftView(APIView):
    """Combined editor draft: the paper document plus its answer key (issue #122).

    GET returns ``{document, answer_document, status}`` for the owner so the
    editor loads both lanes as one review state. PATCH saves both together while
    the paper is a draft, rejecting an answer document that disagrees with the
    paper document (issue #125) so a swapped question can never leave a stale
    answer behind. A separate endpoint from ``PaperDetailView`` so the existing
    exam-document load/save (and the print/PDF consumers) keep their answer-free
    shape untouched.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        paper = get_object_or_404(Paper, pk=pk, created_by=request.user)
        answer_document = self._reconciled_answer_document(paper)

        # Enrich the response copies with backend-issued asset URLs the editor
        # can load (grill decision on #122). The stored documents keep the lean
        # canonical assetId-only shape; the url is non-canonical and request-
        # absolute, so it must never be persisted.
        def url_for(asset_id: str) -> str:
            url = default_storage.url(asset_id)
            # Local storage returns a path-relative URL (MEDIA_URL has no leading
            # slash); force it root-relative so build_absolute_uri anchors it at
            # the host, not the API path. A remote backend (signed S3/CDN) already
            # returns an absolute URL, which is left untouched.
            if "://" not in url and not url.startswith("/"):
                url = "/" + url
            return request.build_absolute_uri(url)

        return Response(
            {
                "document": with_resolved_asset_urls(paper.document, url_for),
                "answer_document": with_resolved_asset_urls(answer_document, url_for),
                "status": paper.status,
            }
        )

    def _reconciled_answer_document(self, paper: Paper) -> dict | None:
        """Answer document consistent with the paper's current document.

        Older drafts assembled before this field gain one lazily; a slot whose
        question was swapped through the legacy paper PATCH (which does not touch
        answers) is refreshed instead of returned stale. The reconciled document
        is persisted when it changed so the fix is durable, not recomputed each
        load. Teacher edits on still-matching slots are preserved by
        ``build_answer_document``.
        """
        if paper.document is None:
            return paper.answer_document
        reconciled = build_answer_document(paper)
        if reconciled != paper.answer_document:
            paper.answer_document = reconciled
            paper.save(update_fields=["answer_document"])
        return reconciled

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
        answer_document = request.data.get("answer_document")
        errors = validate_answer_document(document, answer_document)
        if errors:
            return Response(
                {
                    "error": "Paper and answer documents are inconsistent.",
                    "details": errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Strip the non-canonical asset ``url`` the GET added before persisting,
        # so the editor round-trip never leaks a host-absolute/expiring URL into
        # the stored documents (kept assetId-only, contract §13).
        paper.document = strip_resolved_asset_urls(document)
        paper.answer_document = strip_resolved_asset_urls(answer_document)
        # Bump the revision so a queued AI job (#31) whose base_revision predates
        # this edit is cancelled by the drain instead of spending paid tokens on
        # a now-stale proposal (Rule 13).
        paper.revision = F("revision") + 1
        paper.save(update_fields=["document", "answer_document", "revision"])
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
    teacher's request. Answers are read from the paper-local
    ``answer_document`` (issue #122) by slot id, so the marking scheme reflects
    the teacher's saved/edited answers in current slot order — not live bank
    answers. The exam ``document`` itself still carries no answers. Cached 24h
    once the paper is approved, matching the exam PDF.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        paper = get_object_or_404(Paper, pk=pk, created_by=request.user)
        document = paper.document or {}
        # Reconcile against the current document so a question swapped through the
        # legacy paper PATCH prints its current answer, never a stale one — the
        # join the old live-bank path gave for free, restored at the snapshot.
        answers = printable_answers_by_slot(build_answer_document(paper))
        if paper.status == PaperStatus.APPROVED:
            cache_key = f"paper-answer-key-pdf:{paper.pk}"
            pdf = cache.get(cache_key)
            if pdf is None:
                pdf = render_answer_key_pdf(document, answers)
                cache.set(cache_key, pdf, timeout=_PDF_CACHE_TTL)
        else:
            pdf = render_answer_key_pdf(document, answers)
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = (
            f'inline; filename="paper-{paper.pk}-answer-key.pdf"'
        )
        return response


def _paper_print_url(user, paper_pk: int) -> str | None:
    base_url = settings.PAPER_PRINT_BASE_URL.rstrip("/")
    if not base_url:
        return None
    token, _ = Token.objects.get_or_create(user=user)
    return f"{base_url}/editor/{paper_pk}/print?token={token.key}"
