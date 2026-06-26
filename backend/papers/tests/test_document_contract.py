"""Tests for the server-side PaperDocumentV1 contract guard.

The guard validates a real assembled document against the JSON Schema generated
from the frontend Zod schema (the single source of truth), plus a Python mirror
of the Zod ``.superRefine`` referential-integrity check.
"""

from __future__ import annotations

import copy
from types import SimpleNamespace

import pytest
from rest_framework import status

from papers.builder import PaperBuilder
from papers.document_contract import (
    PaperDocumentContractError,
    validate_paper_document,
)


@pytest.fixture
def document(seeded_bank, api_client) -> dict:
    """A real document assembled via the API — valid by construction."""
    resp = api_client.post("/api/papers/assemble", {}, format="json")
    assert resp.status_code == status.HTTP_201_CREATED
    return resp.data


def test_real_assembled_document_is_contract_valid(document):
    assert validate_paper_document(document) == []


def test_missing_top_level_key_is_flagged(document):
    bad = copy.deepcopy(document)
    del bad["format"]
    errors = validate_paper_document(bad)
    assert any("'format' is a required property" in e for e in errors)


def test_choice_group_missing_display_style_is_flagged(document):
    """The original "Unable to open paper" cause: a choice group without
    displayStyle is now rejected by the schema-derived guard."""
    bad = copy.deepcopy(document)
    bad["questions"][0]["content"] = {"choices": [{"chooseCount": 1, "options": []}]}
    errors = validate_paper_document(bad)
    assert any("displayStyle" in e for e in errors)


def test_slot_referencing_unknown_question_is_flagged(document):
    bad = copy.deepcopy(document)
    slot = bad["paper"]["sections"][0]["slots"][0]
    slot["selectedQuestionId"] = "q_does_not_exist"
    errors = validate_paper_document(bad)
    assert any("unknown question 'q_does_not_exist'" in e for e in errors)


def test_unfilled_slot_is_allowed(document):
    bad = copy.deepcopy(document)
    bad["paper"]["sections"][0]["slots"][0]["selectedQuestionId"] = None
    assert validate_paper_document(bad) == []


def test_contract_error_carries_all_messages():
    err = PaperDocumentContractError(["a", "b"])
    assert err.errors == ["a", "b"]
    assert "a" in str(err) and "b" in str(err)


def test_builder_guard_raises_on_invalid_document(document):
    bad = copy.deepcopy(document)
    del bad["questions"]
    with pytest.raises(PaperDocumentContractError):
        PaperBuilder._guard_contract(SimpleNamespace(pk=1), bad)


def test_builder_guard_passes_valid_document(document):
    PaperBuilder._guard_contract(SimpleNamespace(pk=1), document)
