"""HTTP views for paper assembly, detail, edit, approve, and PDF download.

``AssemblePaperView`` — thin: validate, call PaperBuilder, return document.
``PaperDetailView`` — GET returns stored document; PATCH overwrites it (drafts only).
``PaperApproveView`` — POST locks paper to APPROVED.
``PaperPdfView`` — GET renders PDF from paper.document (cached 24h after approve).
``PaperAnswerKeyPdfView`` — GET renders the separate marking-scheme PDF; the
only path that reveals answers, gated to the paper owner.

Domain rules live in ``papers.builder`` and ``papers.picker``.
"""

import io
import logging
import zipfile
from types import SimpleNamespace

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
from .document import reconcile_document_format_defaults
from .document_contract import PaperDocumentContractError
from .models import Paper, PaperFormat, PaperStatus
from .pdf import render_answer_key_pdf, render_paper_pdf
from .serializers import AssembleRequestSerializer, PaperSerializer
from .template import TemplateBuilder

logger = logging.getLogger(__name__)

_PDF_CACHE_TTL = 60 * 60 * 24  # 1 day
_SCHEMA_VERSION = "paper_document.v1"


def _marks_by_question_type(template) -> dict[str, int]:
    """Total marks by question type, counting OR groups once."""

    seen_or_groups: set[int] = set()
    marks_by_type: dict[str, int] = {}
    for slot in template.slots:
        if slot.or_group is not None:
            if slot.or_group in seen_or_groups:
                continue
            seen_or_groups.add(slot.or_group)
        qtype = slot.qtype.value if hasattr(slot.qtype, "value") else str(slot.qtype)
        marks_by_type[qtype] = marks_by_type.get(qtype, 0) + slot.marks
    return marks_by_type


class PaperFormatsView(APIView):
    """Return available paper formats for the frontend format selector."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        formats = []
        template_builder = TemplateBuilder()
        for paper_format in PaperFormat.objects.filter(is_active=True):
            template = template_builder.build(paper_format.preset_name)
            formats.append(
                {
                    "format_id": paper_format.format_id,
                    "name": paper_format.name,
                    "preset_name": paper_format.preset_name,
                    "total_marks": template.total_marks,
                    "section_count": len({slot.section for slot in template.slots}),
                    "question_count": template.question_count,
                    "marks_by_question_type": _marks_by_question_type(template),
                }
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
        try:
            result = PaperBuilder().assemble(request.user, **params)
        except PaperDocumentContractError as exc:
            # The builder produced a document the editor would reject. Caught
            # and logged in the builder; return a clean 500 instead of a raw
            # traceback or a browser-only "Unable to open paper".
            return Response(
                {
                    "error": "Generated paper failed contract validation.",
                    "detail": exc.errors,
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return Response(result.document, status=status.HTTP_201_CREATED)


class PaperDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        paper = get_object_or_404(Paper, pk=pk, created_by=request.user)
        if paper.document is not None:
            return Response(_document_with_format_defaults(paper))
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
        _document_with_format_defaults(paper)
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
        # Strip the non-canonical asset ``url`` the GET added before persisting,
        # so the editor round-trip never leaks a host-absolute/expiring URL into
        # the stored documents (kept assetId-only, contract §13).
        document = strip_resolved_asset_urls(document)
        answer_document = strip_resolved_asset_urls(request.data.get("answer_document"))
        if not isinstance(answer_document, dict):
            return Response(
                {"error": "answer_document must be an object."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if answer_document.get("schemaVersion") != "paper_answer_document.v1":
            return Response(
                {
                    "error": "answer_document.schemaVersion must be "
                    "'paper_answer_document.v1'."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not isinstance(answer_document.get("answersBySlotId"), dict):
            return Response(
                {"error": "answer_document.answersBySlotId must be an object."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # The frontend cannot know the bank answer for a newly-swapped question.
        # Reconcile before validation so matching teacher-edited answers survive,
        # while changed/missing slot entries are rebuilt from the bank instead of
        # persisting empty placeholders into the answer key.
        answer_document = build_answer_document(
            SimpleNamespace(
                pk=paper.pk,
                document=document,
                answer_document=answer_document,
            )
        )
        errors = validate_answer_document(document, answer_document)
        if errors:
            return Response(
                {
                    "error": "Paper and answer documents are inconsistent.",
                    "details": errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        paper.document = document
        paper.answer_document = answer_document
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
        document = _document_with_format_defaults(paper) or {}
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


class PaperPdfPackageView(APIView):
    """Download the final question paper and answer-key PDFs as one zip."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        paper = get_object_or_404(Paper, pk=pk, created_by=request.user)
        if paper.status == PaperStatus.APPROVED:
            cache_key = f"paper-pdf-package:{paper.pk}"
            package_bytes = cache.get(cache_key)
            if package_bytes is None:
                rendered = self._render_package(request, paper)
                if isinstance(rendered, Response):
                    return rendered
                package_bytes = rendered
                cache.set(cache_key, package_bytes, timeout=_PDF_CACHE_TTL)
        else:
            rendered = self._render_package(request, paper)
            if isinstance(rendered, Response):
                return rendered
            package_bytes = rendered

        response = HttpResponse(package_bytes, content_type="application/zip")
        response["Content-Disposition"] = (
            f'attachment; filename="paper-{paper.pk}-pdfs.zip"'
        )
        return response

    def _render_package(self, request, paper: Paper) -> bytes | Response:
        document = _document_with_format_defaults(paper) or {}
        answers = printable_answers_by_slot(build_answer_document(paper))
        try:
            question_pdf = render_paper_pdf(
                document, print_url=_paper_print_url(request.user, paper.pk)
            )
            answer_key_pdf = render_answer_key_pdf(
                document,
                answers,
                print_url=_answer_key_print_url(request.user, paper.pk),
            )
        except Exception:
            logger.exception("PDF package render failed for paper %s", paper.pk)
            return Response(
                {"error": "Unable to render the PDF package."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        buffer = io.BytesIO()
        with zipfile.ZipFile(
            buffer, mode="w", compression=zipfile.ZIP_DEFLATED
        ) as package:
            package.writestr("question-paper.pdf", question_pdf)
            package.writestr("answer-key.pdf", answer_key_pdf)
        return buffer.getvalue()

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
        print_url = _answer_key_print_url(request.user, paper.pk)
        if paper.status == PaperStatus.APPROVED:
            cache_key = f"paper-answer-key-pdf:{paper.pk}"
            pdf = cache.get(cache_key)
            if pdf is None:
                pdf = render_answer_key_pdf(document, answers, print_url=print_url)
                cache.set(cache_key, pdf, timeout=_PDF_CACHE_TTL)
        else:
            pdf = render_answer_key_pdf(document, answers, print_url=print_url)
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = (
            f'inline; filename="paper-{paper.pk}-answer-key.pdf"'
        )
        return response


def _document_with_format_defaults(paper: Paper) -> dict | None:
    document, changed = reconcile_document_format_defaults(paper.document)
    if changed:
        paper.document = document
        paper.save(update_fields=["document"])
    return document


def _paper_print_url(user, paper_pk: int) -> str | None:
    return _frontend_print_url(user, paper_pk, "print")

def _answer_key_print_url(user, paper_pk: int) -> str | None:
    return _frontend_print_url(user, paper_pk, "answer-key/print")

def _frontend_print_url(user, paper_pk: int, route_suffix: str) -> str | None:
    base_url = settings.PAPER_PRINT_BASE_URL.rstrip("/")
    if not base_url:
        return None
    token, _ = Token.objects.get_or_create(user=user)
    return f"{base_url}/editor/{paper_pk}/{route_suffix}?token={token.key}"
