"""Tests for editor-draft asset URL resolution (issue #122, grill decision).

The editor needs a loadable ``url`` for image assets, but the frontend must not
derive storage paths from the canonical ``assetId``. These tests pin that the
backend adds a non-canonical ``url`` beside every ``assetId`` — wherever it is
nested — without mutating the canonical document.
"""

from __future__ import annotations

from papers.assets import with_resolved_asset_urls


def _url_for(asset_id: str) -> str:
    return f"https://cdn.example.com/{asset_id}"


def test_adds_url_beside_assetid_preserving_canonical():
    item = {"type": "image", "assetId": "diagrams/abc.png"}

    resolved = with_resolved_asset_urls(item, _url_for)

    assert resolved["assetId"] == "diagrams/abc.png"
    assert resolved["url"] == "https://cdn.example.com/diagrams/abc.png"


def test_resolves_assets_nested_in_options():
    """An asset referenced inside an MCQ option must still be resolved — the walk
    is structural, not limited to a top-level stem."""
    document = {
        "questions": [
            {
                "content": {
                    "options": [
                        {
                            "label": "A",
                            "content": [{"type": "image", "assetId": "diagrams/x.png"}],
                        }
                    ]
                }
            }
        ]
    }

    resolved = with_resolved_asset_urls(document, _url_for)

    option = resolved["questions"][0]["content"]["options"][0]
    assert option["content"][0]["url"] == "https://cdn.example.com/diagrams/x.png"


def test_image_placeholder_without_assetid_is_untouched():
    """A placeholder has no asset to resolve, so no url is invented."""
    item = {"type": "image_placeholder", "text": "Diagram pending."}

    assert with_resolved_asset_urls(item, _url_for) == item


def test_does_not_mutate_the_input_document():
    """Enrichment is response-only; the stored canonical document must be left
    asset-URL-free so it never persists a request-absolute url."""
    item = {"type": "image", "assetId": "diagrams/abc.png"}

    with_resolved_asset_urls(item, _url_for)

    assert "url" not in item


def test_none_and_scalars_pass_through():
    assert with_resolved_asset_urls(None, _url_for) is None
    assert with_resolved_asset_urls("text", _url_for) == "text"
