"""Tests for the server-side PaperDocumentV1 contract guard."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from papers.builder import PaperBuilder
from papers.document_contract import (
    PaperDocumentContractError,
    validate_paper_document,
)


def _document(**overrides) -> dict:
    doc = {
        "schemaVersion": "paper_document.v1",
        "request": {},
        "template": {},
        "format": {},
        "questions": [
            {"id": "q_1", "content": {"stem": []}},
            {
                "id": "q_2",
                "content": {
                    "choices": [{"displayStyle": "or", "chooseCount": 1, "options": []}]
                },
            },
        ],
        "paper": {
            "sections": [
                {
                    "slots": [
                        {"id": "slot_A_01", "selectedQuestionId": "q_1"},
                        {
                            "id": "slot_C_01",
                            "selectedQuestionId": "q_2",
                            "alternateQuestionIds": ["q_1"],
                        },
                    ]
                }
            ]
        },
    }
    doc.update(overrides)
    return doc


def test_valid_document_has_no_errors():
    assert validate_paper_document(_document()) == []


def test_missing_top_level_key_is_flagged():
    doc = _document()
    del doc["format"]
    assert any("missing required keys" in e for e in validate_paper_document(doc))


def test_choice_group_missing_display_style_is_flagged():
    # A row that slipped past normalisation: choices without displayStyle.
    doc = _document()
    doc["questions"][1]["content"]["choices"][0].pop("displayStyle")
    errors = validate_paper_document(doc)
    assert any("displayStyle must be one of" in e for e in errors)


def test_slot_referencing_unknown_question_is_flagged():
    doc = _document()
    doc["paper"]["sections"][0]["slots"][0]["selectedQuestionId"] = "q_999"
    errors = validate_paper_document(doc)
    assert any("unknown question id 'q_999'" in e for e in errors)


def test_unfilled_slot_is_allowed():
    doc = _document()
    doc["paper"]["sections"][0]["slots"][0]["selectedQuestionId"] = None
    assert validate_paper_document(doc) == []


def test_contract_error_carries_all_messages():
    err = PaperDocumentContractError(["a", "b"])
    assert err.errors == ["a", "b"]
    assert "a" in str(err) and "b" in str(err)


def test_builder_guard_raises_on_invalid_document():
    """A document the editor would reject fails loudly at assembly, not in the
    browser. Uses an unrepairable group (displayStyle present but bogus) so
    normalisation can't fix it."""
    doc = _document()
    doc["questions"][1]["content"]["choices"][0]["displayStyle"] = "bogus"
    with pytest.raises(PaperDocumentContractError):
        PaperBuilder._guard_contract(SimpleNamespace(pk=1), doc)


def test_builder_guard_passes_valid_document():
    PaperBuilder._guard_contract(SimpleNamespace(pk=1), _document())
