"""AI editor proposal guardrails.

These pin the deterministic boundary that protects canonical paper state from
unsafe model output (PRD #30, issue #32): allowed chrome edits pass, and every
forbidden category the PRD enumerates is rejected with a *named, user-safe*
guard — so the test fails loudly if a future change quietly widens what the AI
can touch (Rule 9: the why is "the model is never the source of truth for
safety"). The guard id set is mirrored on the frontend; the parity test pins it.
"""

import pytest

from ai_editor.proposals import (
    GUARD_MESSAGES,
    MAX_PATCHES,
    EditProposal,
    build_refusal,
    validate_proposal,
)

# A two-section paper with stable ids, mirroring PaperDocumentV1 (contracts/).
DOCUMENT = {
    "paper": {
        "title": "Science — Mock",
        "subtitle": "Class 10",
        "chromeBlocks": [{"id": "chrome-1", "role": "masthead", "text": "Header"}],
        "instructionBlocks": [
            {"id": "instr-1", "role": "general", "text": "Answer all questions."}
        ],
        "sections": [
            {
                "id": "section-a",
                "title": "Section A",
                "subtitle": "Objective",
                "instructions": "Answer any four questions.",
                "marks": 5,
                "slots": [
                    {"id": "slot-a1", "marks": 2, "selectedQuestionId": "q1"},
                    {"id": "slot-a2", "marks": 3, "selectedQuestionId": "q2"},
                ],
            },
            {
                "id": "section-b",
                "title": "Section B",
                "marks": 4,
                "slots": [{"id": "slot-b1", "marks": 4, "selectedQuestionId": "q3"}],
            },
        ],
    },
    "format": {
        "page": {"size": "A4", "orientation": "portrait"},
        "layout": {
            "marks": "right",
            "questionNumbers": "left",
            "mcqOptions": "inline",
            "instructions": "top",
            "masthead": "centered",
            "footer": "page_numbers",
        },
    },
    "questions": [{"id": "q1"}, {"id": "q2"}, {"id": "q3"}],
}

REVISION = 7


def _validate(patches, *, base=REVISION, current=REVISION):
    proposal = EditProposal(patches=patches)
    return validate_proposal(
        DOCUMENT, proposal, base_revision=base, current_revision=current
    )


def _guard_ids(result):
    return {entry["guardId"] for entry in result["blocking"]}


# --- Allowed chrome edits pass ------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "/paper/title",
        "/paper/subtitle",
        "/paper/chromeBlocks/chrome-1/text",
        "/paper/instructionBlocks/instr-1/text",
        "/paper/sections/section-a/title",
        "/paper/sections/section-a/subtitle",
        "/paper/sections/section-a/instructions",
        "/format/page/size",
        "/format/layout/marks",
    ],
)
def test_allowed_chrome_paths_have_no_blocking_guard(path):
    result = _validate([{"op": "replace", "path": path, "value": "New value"}])
    assert result["blocking"] == []


def test_allowed_marks_edit_passes_but_warns_on_recomputed_total():
    # Marks edits are allowed; the proposal must never be trusted to assert the
    # new total, so a valid marks change surfaces a recompute warning instead.
    result = _validate(
        [
            {
                "op": "replace",
                "path": "/paper/sections/section-a/slots/slot-a1/marks",
                "value": 4,
                "oldValue": 2,
            }
        ]
    )
    assert result["blocking"] == []
    assert result["warnings"] == ["Total marks changed from 9 to 11."]


def test_marks_edit_with_no_net_change_does_not_warn():
    result = _validate(
        [
            {
                "op": "replace",
                "path": "/paper/sections/section-a/slots/slot-a1/marks",
                "value": 2,
            }
        ]
    )
    assert result["warnings"] == []


# --- Forbidden categories are each rejected with a named guard -----------------


@pytest.mark.parametrize(
    ("path", "expected_guard"),
    [
        ("/questions/q1/content/stem/0/text", "forbidden_question_text"),
        ("/questions/q1/rawText", "forbidden_question_text"),
        ("/questions/q1/source/name", "forbidden_question_source"),
        ("/questions/q1/metadata/difficulty", "forbidden_question_source"),
        (
            "/paper/sections/section-a/slots/slot-a1/selectedQuestionId",
            "forbidden_question_swap",
        ),
        ("/paper/sections/section-a/slots", "forbidden_question_count"),
        ("/paper/sections/section-a/slots/slot-a1", "forbidden_question_count"),
        ("/paper/sections", "forbidden_section_membership"),
        ("/paper/sections/section-a", "forbidden_section_membership"),
        ("/paper/totalMarks", "forbidden_path"),
        ("/paper/sections/section-a/marks", "forbidden_path"),
    ],
)
def test_forbidden_path_rejected_with_named_guard(path, expected_guard):
    result = _validate([{"op": "replace", "path": path, "value": "x"}])
    assert expected_guard in _guard_ids(result)


def test_non_replace_operation_is_unsupported():
    # add/remove/move would change question count or section membership; only
    # replace of an existing field is ever allowed.
    for op in ("add", "remove", "move", "copy"):
        result = _validate([{"op": op, "path": "/paper/title", "value": "x"}])
        assert "unsupported_operation" in _guard_ids(result)


def test_cross_section_move_is_rejected():
    result = _validate(
        [
            {
                "op": "move",
                "path": "/paper/sections/section-b/slots/slot-a1",
                "value": None,
            }
        ]
    )
    assert "unsupported_operation" in _guard_ids(result)


def test_raw_blocknote_value_on_allowed_path_is_rejected():
    # A structured value where plain text/number is expected is the BlockNote
    # JSON the model must not smuggle through an otherwise-allowed path.
    result = _validate(
        [
            {
                "op": "replace",
                "path": "/paper/title",
                "value": [{"type": "paragraph", "content": []}],
            }
        ]
    )
    assert "forbidden_raw_content" in _guard_ids(result)


def test_unknown_target_id_is_rejected():
    result = _validate(
        [
            {
                "op": "replace",
                "path": "/paper/sections/section-z/instructions",
                "value": "x",
            }
        ]
    )
    assert "unknown_target" in _guard_ids(result)


def test_slot_under_wrong_section_is_an_unknown_target():
    # slot-a1 lives in section-a; addressing it under section-b must not resolve,
    # or the AI could quietly move a question across sections.
    result = _validate(
        [
            {
                "op": "replace",
                "path": "/paper/sections/section-b/slots/slot-a1/marks",
                "value": 5,
            }
        ]
    )
    assert "unknown_target" in _guard_ids(result)


@pytest.mark.parametrize(
    "path",
    [
        "/paper/chromeBlocks/instr-1/text",  # instr-1 is an instruction block
        "/paper/instructionBlocks/chrome-1/text",  # chrome-1 is a chrome block
    ],
)
def test_block_id_must_live_in_the_collection_its_path_names(path):
    # Deny-by-default: a chrome path must not resolve an instruction block (or
    # vice versa), or the AI could target the wrong block and the apply would
    # land on the wrong element or silently no-op.
    result = _validate([{"op": "replace", "path": path, "value": "x"}])
    assert "unknown_target" in _guard_ids(result)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("hello", "forbidden_value_type"),
        (True, "forbidden_value_type"),
        ([], "forbidden_raw_content"),  # non-scalar caught first
    ],
)
def test_non_numeric_marks_value_is_rejected(value, expected):
    # marks is numeric in the contract; a string/bool would corrupt canonical
    # state on apply even though it is a scalar.
    result = _validate(
        [
            {
                "op": "replace",
                "path": "/paper/sections/section-a/slots/slot-a1/marks",
                "value": value,
            }
        ]
    )
    assert expected in _guard_ids(result)


def test_numeric_value_on_a_text_field_is_rejected():
    result = _validate([{"op": "replace", "path": "/paper/title", "value": 5}])
    assert "forbidden_value_type" in _guard_ids(result)


def test_oversized_proposal_is_rejected():
    patches = [
        {"op": "replace", "path": "/paper/title", "value": "x"}
        for _ in range(MAX_PATCHES + 1)
    ]
    result = _validate(patches)
    assert "proposal_too_large" in _guard_ids(result)


def test_stale_base_revision_is_rejected():
    result = _validate(
        [{"op": "replace", "path": "/paper/title", "value": "New"}],
        base=REVISION - 1,
        current=REVISION,
    )
    assert "stale_base_revision" in _guard_ids(result)


def test_stale_revision_suppresses_recompute_warning():
    # A blocked proposal will not apply, so marks-recompute noise would mislead.
    result = _validate(
        [
            {
                "op": "replace",
                "path": "/paper/sections/section-a/slots/slot-a1/marks",
                "value": 9,
            }
        ],
        base=REVISION - 1,
    )
    assert result["warnings"] == []


def test_blocking_entries_carry_user_safe_message_and_path():
    result = _validate(
        [{"op": "replace", "path": "/questions/q1/rawText", "value": "x"}]
    )
    entry = result["blocking"][0]
    assert entry["path"] == "/questions/q1/rawText"
    assert entry["message"] == GUARD_MESSAGES["forbidden_question_text"]
    # User-safe: no path/JSON jargon leaks into the message.
    assert "/" not in entry["message"]


def test_duplicate_guard_path_pairs_are_collapsed():
    result = _validate(
        [
            {"op": "replace", "path": "/questions/q1/rawText", "value": "a"},
            {"op": "replace", "path": "/questions/q1/rawText", "value": "b"},
        ]
    )
    assert len(result["blocking"]) == 1


def test_guard_id_registry_is_the_pinned_contract():
    # This set is mirrored verbatim in frontend/src/types/ai-proposal.schema.ts
    # and documented in contracts/ai_proposal.v1.md. Adding or renaming a guard
    # here without updating both is a contract drift this test catches.
    assert set(GUARD_MESSAGES) == {
        "stale_base_revision",
        "proposal_too_large",
        "unsupported_operation",
        "unknown_target",
        "forbidden_question_text",
        "forbidden_question_source",
        "forbidden_question_swap",
        "forbidden_question_count",
        "forbidden_section_membership",
        "forbidden_raw_content",
        "forbidden_value_type",
        "forbidden_path",
    }


def test_build_refusal_shape():
    refusal = build_refusal("I cannot rewrite sourced question text.", ["x"])
    assert refusal == {
        "status": "refused",
        "message": "I cannot rewrite sourced question text.",
        "brokenGuards": ["x"],
    }
