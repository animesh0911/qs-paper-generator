"""Tests for the score_extraction scorer.

Pure-function tests over synthetic extraction + ground-truth dicts — no LLM, no
DB. They pin the metric semantics: substring-key matching, recall/precision,
section/qtype accuracy over matched pairs, and missed/spurious accounting.
"""

from __future__ import annotations

from bank.management.commands.score_extraction import score


def _gt(*questions: dict) -> dict:
    return {"questions": list(questions)}


def _ext(*questions: dict) -> dict:
    return {"questions": list(questions)}


def _mcq(text, section="A", qtype="mcq", marks=1, options=None):
    return {
        "text": text,
        "section": section,
        "qtype": qtype,
        "marks": marks,
        "options": (
            options
            if options is not None
            else [{"label": x, "text": x} for x in "ABCD"]
        ),
        "content": {},
    }


def test_perfect_match_scores_one():
    """All ground-truth keys found, no extras → recall=precision=1."""
    gt = _gt(
        {
            "num": 1,
            "section": "A",
            "qtype": "mcq",
            "marks": 1,
            "key": "gaseous exchange",
        }
    )
    ext = _ext(_mcq("Which structure handles gaseous exchange in a leaf?"))

    r = score(ext, gt)

    assert r["recall"] == 1.0
    assert r["precision"] == 1.0
    assert r["section_accuracy"] == 1.0
    assert r["missed"] == []
    assert r["spurious"] == []


def test_missed_question_lowers_recall():
    """A ground-truth entry with no matching extraction is reported missed."""
    gt = _gt(
        {
            "num": 1,
            "section": "A",
            "qtype": "mcq",
            "marks": 1,
            "key": "gaseous exchange",
        },
        {
            "num": 2,
            "section": "D",
            "qtype": "long_answer",
            "marks": 5,
            "key": "ohm's law",
        },
    )
    ext = _ext(_mcq("Which structure handles gaseous exchange?"))

    r = score(ext, gt)

    assert r["recall"] == 0.5
    assert [m["num"] for m in r["missed"]] == [2]


def test_spurious_extraction_lowers_precision():
    """An extracted row matching no ground-truth key is reported spurious."""
    gt = _gt(
        {
            "num": 1,
            "section": "A",
            "qtype": "mcq",
            "marks": 1,
            "key": "gaseous exchange",
        }
    )
    ext = _ext(
        _mcq("Which structure handles gaseous exchange?"),
        _mcq("Directions: questions 8 and 9 are assertion-reason", qtype="mcq"),
    )

    r = score(ext, gt)

    assert r["recall"] == 1.0
    assert r["precision"] == 0.5
    assert len(r["spurious"]) == 1


def test_wrong_section_counts_against_section_accuracy():
    """A matched pair with the wrong section dings section accuracy, not recall.

    Why this matters: the marks→section derivation is a distinct failure mode
    from recall; the scorer must separate 'found it' from 'filed it right'."""
    gt = _gt(
        {
            "num": 1,
            "section": "B",
            "qtype": "short_answer",
            "marks": 2,
            "key": "diaphragm",
        }
    )
    ext = _ext(
        {
            "text": "What is the function of the diaphragm?",
            "section": "C",  # wrong — marks misread
            "qtype": "short_answer",
            "marks": 3,
            "options": [],
            "content": {"stem": [{"type": "paragraph", "text": "x"}]},
        }
    )

    r = score(ext, gt)

    assert r["recall"] == 1.0
    assert r["section_accuracy"] == 0.0


def test_key_matches_text_in_content_regions():
    """A key found only in assertion/reason or nested choices still matches.

    Why this matters: thin-stem types (assertion-reason, differences,
    internal-choice) carry their identifying wording in content regions, not the
    stem. If matching looked only at the stem, every such question would read as
    missed and recall would be meaningless for the bulk of a real paper."""
    gt = _gt(
        {
            "num": 1,
            "section": "A",
            "qtype": "assertion_reason",
            "marks": 1,
            "key": "reflex actions do not involve thinking",
        },
        {
            "num": 2,
            "section": "C",
            "qtype": "internal_choice",
            "marks": 3,
            "key": "chlor-alkali process",
        },
    )
    ext = _ext(
        {
            "text": "",  # AR question has no stem; wording lives in content
            "section": "A",
            "qtype": "assertion_reason",
            "marks": 1,
            "options": [],
            "content": {
                "assertion": [
                    {
                        "type": "paragraph",
                        "text": "Reflex actions do not involve thinking.",
                    }
                ],
                "reason": [
                    {
                        "type": "paragraph",
                        "text": "Controlled by the spinal cord.",
                    }
                ],
            },
        },
        {
            "text": "",  # internal-choice wording lives in nested choices
            "section": "C",
            "qtype": "internal_choice",
            "marks": 3,
            "options": [],
            "content": {
                "choices": [
                    {
                        "displayStyle": "or",
                        "chooseCount": 1,
                        "options": [
                            {
                                "label": "a",
                                "content": [
                                    {
                                        "type": "paragraph",
                                        "text": "Explain chlor-alkali process "
                                        "with chemical equation.",
                                    }
                                ],
                            },
                            {
                                "label": "b",
                                "content": [
                                    {
                                        "type": "paragraph",
                                        "text": "Write the preparation of "
                                        "baking soda.",
                                    }
                                ],
                            },
                        ],
                    }
                ]
            },
        },
    )

    r = score(ext, gt)

    assert r["recall"] == 1.0
    assert r["missed"] == []


def test_duplicate_key_matches_only_one_extraction():
    """One ground-truth entry consumes at most one extracted question.

    Why this matters: without claiming, a single truth key would match every
    near-identical extracted row and mask over-extraction."""
    gt = _gt(
        {
            "num": 1,
            "section": "A",
            "qtype": "mcq",
            "marks": 1,
            "key": "gaseous exchange",
        }
    )
    ext = _ext(
        _mcq("Which structure handles gaseous exchange?"),
        _mcq("Gaseous exchange happens where? (duplicate)"),
    )

    r = score(ext, gt)

    assert r["matched"] == 1
    assert len(r["spurious"]) == 1
