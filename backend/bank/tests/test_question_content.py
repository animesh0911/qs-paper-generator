"""Unit tests for the shared Question content normaliser + validator."""

from __future__ import annotations

from bank.question_content import (
    normalise_question_content,
    validate_question_content,
)


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


def test_validate_accepts_normalised_choice_group():
    assert validate_question_content({"choices": [_group()]}) == []


def test_validate_flags_bad_display_style_and_types():
    content = {
        "choices": [
            {"displayStyle": "maybe", "chooseCount": "1", "options": {}},
        ]
    }

    errors = validate_question_content(content)

    assert any("displayStyle must be one of" in e for e in errors)
    assert any("chooseCount must be an integer" in e for e in errors)
    assert any("options must be a list" in e for e in errors)


def test_validate_flags_non_dict_content():
    assert validate_question_content("nope") == ["content must be an object"]
