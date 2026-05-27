from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .assembler import assemble_paper
from .models import Paper
from .pdf import render_paper_pdf
from .serializers import PaperSerializer


class AssemblePaperView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        title = request.data.get("title") or "Science — Practice Paper"
        paper = assemble_paper(request.user, title=title)
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
        pdf = render_paper_pdf(paper)
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="paper-{paper.pk}.pdf"'
        return response
