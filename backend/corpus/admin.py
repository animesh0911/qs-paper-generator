"""Django admin inspection surfaces for the canonical NCERT corpus."""

from django.contrib import admin

from .models import RetrievalChunk, TextbookDocument, TextbookElement


@admin.register(TextbookDocument)
class TextbookDocumentAdmin(admin.ModelAdmin):
    list_display = (
        "chapter",
        "source_file_name",
        "extractor_name",
        "extractor_version",
        "page_count",
    )
    readonly_fields = ("source_hash", "canonical_json_hash", "created_at")


@admin.register(TextbookElement)
class TextbookElementAdmin(admin.ModelAdmin):
    list_display = (
        "document",
        "source_order",
        "element_type",
        "page_number",
        "short_text",
    )
    list_filter = ("document", "element_type", "page_number")
    search_fields = ("text", "stable_element_id")
    readonly_fields = ("stable_element_id",)
    ordering = ("document", "source_order")

    @admin.display(description="Text")
    def short_text(self, obj):
        return obj.text[:100]


@admin.register(RetrievalChunk)
class RetrievalChunkAdmin(admin.ModelAdmin):
    list_display = (
        "chapter",
        "chapter_map_node",
        "page_start",
        "page_end",
        "embedding_model",
        "embedding_version",
        "embedding_dimensions",
    )
    list_filter = (
        "chapter",
        "chapter_map_node",
        "embedding_model",
        "embedding_version",
        "embedding_dimensions",
    )
    search_fields = ("text", "stable_chunk_id")
    readonly_fields = (
        "stable_chunk_id",
        "search_vector",
        "embedding",
        "embedding_model",
        "embedding_version",
        "embedding_dimensions",
    )
