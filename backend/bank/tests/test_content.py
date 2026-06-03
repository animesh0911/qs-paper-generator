"""Tests for bank.content — the one tree-walk over the structured Content shape.

These pin the behaviour every caller now depends on (ingestor has_diagram,
document requiresTable, pdf flatten, cropper placement) so a change to the walk
fails here once instead of silently shifting three call-sites.
"""

from __future__ import annotations

from bank import content as content_mod


def test_has_item_finds_nested_image_inside_choices():
    """The walk reaches into `choices` → options → content.

    Why this matters: the hand-written scanner this replaced stopped at the
    choice-group level, so a figure inside an internal-choice option was invisible
    to has_diagram. The unified walk is exhaustive — a stricter, more honest gate.
    """
    content = {
        "choices": [
            {
                "displayStyle": "or",
                "chooseCount": 1,
                "options": [
                    {"label": "A", "content": [{"type": "paragraph", "text": "x"}]},
                    {
                        "label": "B",
                        "content": [{"type": "image", "assetId": "d/1.png"}],
                    },
                ],
            }
        ]
    }
    assert content_mod.has_item(content, "image") is True
    assert content_mod.has_item(content, "table") is False


def test_has_item_on_non_container_is_false():
    assert content_mod.has_item(None, "image") is False
    assert content_mod.has_item("not a tree", "image") is False


def test_has_item_finds_table_nested_in_labelled_region():
    content = {
        "stem": [{"type": "paragraph", "text": "p"}],
        "subparts": [{"label": "i", "content": [{"type": "table", "rows": []}]}],
    }
    assert content_mod.has_item(content, "table") is True


def test_flatten_text_joins_paragraph_text_and_trims():
    items = [
        {"type": "paragraph", "text": "Define"},
        {"type": "paragraph", "text": "refraction."},
    ]
    assert content_mod.flatten_text(items) == "Define refraction."
    assert content_mod.flatten_text(None) == ""


def test_place_item_upgrades_placeholder_in_item_region():
    """An item-region figure swaps the first placeholder, not appends beside it."""
    content = {
        "stem": [
            {"type": "paragraph", "text": "Draw it."},
            {"type": "image_placeholder", "text": "field"},
        ]
    }
    content_mod.place_item(content, "stem", {"type": "image", "assetId": "d/1.png"})

    types = [it["type"] for it in content["stem"]]
    assert types == ["paragraph", "image"]
    assert "image_placeholder" not in types


def test_place_item_targets_labelled_entry_case_insensitively():
    content = {
        "options": [
            {"label": "A", "content": [{"type": "image_placeholder", "text": "A"}]},
            {"label": "B", "content": [{"type": "image_placeholder", "text": "B"}]},
        ]
    }
    content_mod.place_item(
        content, "options", {"type": "image", "assetId": "d/2.png"}, label="b"
    )

    opt_a, opt_b = content["options"]
    assert opt_a["content"][0]["type"] == "image_placeholder"  # untouched
    assert opt_b["content"][0]["type"] == "image"


def test_place_item_no_matching_label_is_noop():
    """An unmatched label leaves every placeholder in place (figure soft-misses)."""
    content = {
        "options": [
            {"label": "A", "content": [{"type": "image_placeholder", "text": "A"}]},
        ]
    }
    content_mod.place_item(
        content, "options", {"type": "image", "assetId": "d/3.png"}, label="Z"
    )
    assert content["options"][0]["content"][0]["type"] == "image_placeholder"
