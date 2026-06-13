"""Authenticated read-only endpoints for corpus chapter maps.

Documents are always addressed by explicit TextbookDocument identity so
multiple extractions of one canonical Chapter never resolve ambiguously.
"""

from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import ChapterMapNode, TextbookDocument
from .serializers import (
    ChapterMapEdgeSerializer,
    ChapterMapNodeSerializer,
    TextbookDocumentMapSerializer,
    TextbookElementSourceSerializer,
)


@api_view(["GET"])
def chapter_map(request, document_id):
    document = get_object_or_404(
        TextbookDocument.objects.select_related("chapter"), pk=document_id
    )
    nodes = document.chapter_map_nodes.select_related("parent", "source_element").all()
    edges = document.chapter_map_edges.select_related(
        "source", "target", "evidence_element"
    ).all()
    return Response(
        {
            "document": TextbookDocumentMapSerializer(document).data,
            "nodes": ChapterMapNodeSerializer(nodes, many=True).data,
            "edges": ChapterMapEdgeSerializer(edges, many=True).data,
        }
    )


@api_view(["GET"])
def chapter_map_node_details(request, document_id, stable_node_id):
    node = get_object_or_404(
        ChapterMapNode.objects.select_related("parent", "source_element"),
        document_id=document_id,
        stable_node_id=stable_node_id,
    )
    elements = list(
        node.document.elements.filter(
            source_order__gte=node.source_start,
            source_order__lte=node.source_end,
        ).order_by("source_order")
    )
    excerpt = " ".join(element.text for element in elements if element.text)[:2000]
    assets = [
        {
            "element_id": element.stable_element_id,
            "type": element.element_type,
            "path": element.asset_path,
        }
        for element in elements
        if element.asset_path
    ]
    return Response(
        {
            "node": ChapterMapNodeSerializer(node).data,
            "source": {
                "elements": TextbookElementSourceSerializer(elements, many=True).data,
                "excerpt": excerpt,
                "pages": sorted({element.page_number for element in elements}),
                "element_types": sorted({element.element_type for element in elements}),
                "assets": assets,
            },
        }
    )
