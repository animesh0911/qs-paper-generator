"""Unit tests for the shared Question content normaliser + validator."""

from __future__ import annotations

from bank.question_content import normalise_question_content, repair_stem


def _group(**overrides):
    base = {
        "displayStyle": "or",
        "chooseCount": 1,
        "options": [
            {"label": "i", "content": [{"type": "paragraph", "text": "A"}]},
            {"label": "ii", "content": [{"type": "paragraph", "text": "B"}]},
        ],
    }
    base.update(overrides)
    return base


def test_normalise_fills_missing_display_style_and_choose_count():
    group = _group()
    del group["displayStyle"]
    del group["chooseCount"]
    content = {"choices": [group]}

    result = normalise_question_content(content)

    assert result["choices"][0]["displayStyle"] == "or"
    assert result["choices"][0]["chooseCount"] == 1
    # Input is not mutated.
    assert "displayStyle" not in content["choices"][0]


def test_normalise_preserves_existing_display_style():
    content = {"choices": [_group(displayStyle="choose_any", chooseCount=2)]}

    result = normalise_question_content(content)

    assert result is content  # nothing to repair → same object
    assert result["choices"][0]["displayStyle"] == "choose_any"
    assert result["choices"][0]["chooseCount"] == 2


def test_normalise_ignores_content_without_choices():
    content = {"stem": [{"type": "paragraph", "text": "Q"}]}
    assert normalise_question_content(content) is content


def test_normalise_ignores_non_dict_content():
    assert normalise_question_content("nope") == "nope"


def test_repair_stem_rebuilds_contentless_stem_from_text():
    """A stem that flattened to a bare label is replaced by the real text."""
    content = {"stem": [{"type": "paragraph", "text": "(b)"}]}
    result = repair_stem(content, "(b) (i) Draw a schematic diagram of a circuit.")
    assert result["stem"] == [
        {"type": "paragraph", "text": "(b) (i) Draw a schematic diagram of a circuit."}
    ]


def test_repair_stem_rebuilds_empty_stem_from_text():
    result = repair_stem({}, "Define velocity.")
    assert result["stem"] == [{"type": "paragraph", "text": "Define velocity."}]


def test_repair_stem_leaves_good_stem_untouched():
    """A stem with real content is returned unchanged (same object)."""
    content = {"stem": [{"type": "paragraph", "text": "What is photosynthesis?"}]}
    assert repair_stem(content, "ignored") is content


def test_repair_stem_no_op_when_text_also_contentless():
    """Nothing to recover from — both stem and text are fragments."""
    content = {"stem": [{"type": "paragraph", "text": "(b)"}]}
    assert repair_stem(content, "39. (a)") is content
