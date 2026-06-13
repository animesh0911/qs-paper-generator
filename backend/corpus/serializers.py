"""Renderer-neutral serializers for persisted corpus chapter maps.

The API exposes stable semantic identities, source evidence, and inclusive
ranges. Layout coordinates and renderer-specific graph fields do not belong in
this module.
"""

from rest_framework import serializers

from bank.serializers import ChapterSerializer

from .models import (
    ChapterMapEdge,
    ChapterMapNode,
    TextbookDocument,
    TextbookElement,
)


class TextbookDocumentMapSerializer(serializers.ModelSerializer):
    chapter = ChapterSerializer(read_only=True)

    class Meta:
        model = TextbookDocument
        fields = ["id", "chapter", "source_file_name", "page_count"]


class ChapterMapNodeSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source="stable_node_id")
    type = serializers.CharField(source="node_type")
    parent_id = serializers.CharField(source="parent.stable_node_id", allow_null=True)
    source_element_id = serializers.CharField(
        source="source_element.stable_element_id", allow_null=True
    )
    source_range = serializers.SerializerMethodField()
    page_range = serializers.SerializerMethodField()

    class Meta:
        model = ChapterMapNode
        fields = [
            "id",
            "type",
            "title",
            "parent_id",
            "source_element_id",
            "source_range",
            "page_range",
            "element_count",
            "preview",
        ]

    def get_source_range(self, obj):
        return {"start": obj.source_start, "end": obj.source_end}

    def get_page_range(self, obj):
        return {"start": obj.page_start, "end": obj.page_end}


class ChapterMapEdgeSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source="stable_edge_id")
    type = serializers.CharField(source="edge_type")
    source_id = serializers.CharField(source="source.stable_node_id")
    target_id = serializers.CharField(source="target.stable_node_id")
    evidence_element_id = serializers.CharField(
        source="evidence_element.stable_element_id", allow_null=True
    )

    class Meta:
        model = ChapterMapEdge
        fields = [
            "id",
            "type",
            "source_id",
            "target_id",
            "evidence_element_id",
        ]


class TextbookElementSourceSerializer(serializers.ModelSerializer):
    element_id = serializers.CharField(source="stable_element_id")
    type = serializers.CharField(source="element_type")

    class Meta:
        model = TextbookElement
        fields = [
            "element_id",
            "type",
            "source_order",
            "page_number",
            "bbox",
            "heading_path",
            "text",
            "structured_data",
            "asset_path",
        ]
