"""HTTP views for paper assembly, detail, edit, approve, and PDF download.

``AssemblePaperView`` — thin: validate, call PaperBuilder, return document.
``PaperDetailView`` — GET returns stored document; PATCH overwrites it (drafts only).
``PaperApproveView`` — POST locks paper to APPROVED.
``PaperPdfView`` — GET renders PDF from paper.document (cached 24h after approve).

Domain rules live in ``papers.builder`` and ``papers.picker``.
"""

from django.core.cache import cache
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from bank.models import Question

from .builder import PaperBuilder
from .models import Paper, PaperStatus
from .pdf import render_paper_pdf
from .serializers import AssembleRequestSerializer, PaperSerializer

_PDF_CACHE_TTL = 60 * 60 * 24  # 1 day
_SCHEMA_VERSION = "paper_document.v1"


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
        errors = validate_paper_document(document)
        if errors:
            return Response({"errors": errors}, status=status.HTTP_400_BAD_REQUEST)
        paper.document = document
        paper.save(update_fields=["document"])
        cache.delete(f"paper-pdf:{paper.pk}")
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
        document = request.data.get("document", paper.document)
        if (
            not isinstance(document, dict)
            or document.get("schemaVersion") != _SCHEMA_VERSION
        ):
            return Response(
                {"error": f"document.schemaVersion must be '{_SCHEMA_VERSION}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        errors = validate_paper_document(document)
        if errors:
            return Response({"errors": errors}, status=status.HTTP_400_BAD_REQUEST)
        paper.document = document
        paper.status = PaperStatus.APPROVED
        paper.save(update_fields=["document", "status"])
        cache.delete(f"paper-pdf:{paper.pk}")
        # ADR-0002: verification emerges from approval. Flip every referenced
        # question to verified=True. Idempotent (already-verified rows no-op).
        Question.objects.filter(pk__in=selected_question_pks(document)).update(
            verified=True
        )
        return Response({"paperId": f"paper_{paper.pk}", "status": paper.status})


class PaperPdfView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        paper = get_object_or_404(Paper, pk=pk, created_by=request.user)
        cache_key = f"paper-pdf:{paper.pk}"
        pdf = cache.get(cache_key)
        if pdf is None:
            pdf = render_paper_pdf(paper.document or {})
            cache.set(cache_key, pdf, timeout=_PDF_CACHE_TTL)
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="paper-{paper.pk}.pdf"'
        return response


def validate_paper_document(document: dict) -> list[str]:
    """Return structural errors that make a PaperDocumentV1 unsafe to freeze."""
    errors: list[str] = []
    questions_by_id = {
        question.get("questionId"): question
        for question in document.get("questions", [])
    }
    language = document.get("paper", {}).get("language")

    for section in document.get("paper", {}).get("sections", []):
        for slot in section.get("slots", []):
            referenced_question_ids = [
                slot.get("selectedQuestionId"),
                *slot.get("alternateQuestionIds", []),
            ]
            for question_id in filter(None, referenced_question_ids):
                question = questions_by_id.get(question_id)
                if question is None:
                    errors.append(
                        f"{slot.get('slotId')} references missing {question_id}."
                    )
                    continue
                if (
                    question.get("marks") != slot.get("marks")
                    or question.get("questionType") != slot.get("questionType")
                    or question.get("language") != language
                ):
                    errors.append(
                        f"{slot.get('slotId')} references incompatible {question_id}."
                    )
    return errors


def selected_question_pks(document: dict) -> list[int]:
    """Extract database primary keys from final selected ``q_<pk>`` identifiers."""
    pks: list[int] = []
    for section in document.get("paper", {}).get("sections", []):
        for slot in section.get("slots", []):
            question_id = slot.get("selectedQuestionId")
            if not isinstance(question_id, str) or not question_id.startswith("q_"):
                continue
            raw_pk = question_id.removeprefix("q_")
            if raw_pk.isdigit():
                pks.append(int(raw_pk))
    return pks
