"""Tests for the benchmark_extraction runner.

Pure-function tests over synthetic manifests + extractions — no LLM, no DB.
They pin the harness semantics that ``score_extraction``'s own tests don't:
multi-manifest aggregation into one table, multi-arm A/B ordering, and a loud
``missing`` row when an arm has no extraction for a paper (Rule 12).
"""

from __future__ import annotations

from bank.management.commands.benchmark_extraction import build_rows, format_table


def _mcq(text, section="A", qtype="mcq", marks=1):
    return {
        "text": text,
        "section": section,
        "qtype": qtype,
        "marks": marks,
        "options": [{"label": x, "text": x} for x in "ABCD"],
        "content": {},
    }


def _gt(paper, *questions):
    return paper, {"source_pdf": f"{paper}.pdf", "questions": list(questions)}


def _entry(num, key, section="A", qtype="mcq", marks=1):
    return {"num": num, "section": section, "qtype": qtype, "marks": marks, "key": key}


def test_rows_cover_every_paper_arm_pair_paper_major():
    """One row per (paper, arm), ordered paper-major then arm-minor.

    Why this matters: a benchmark table that silently drops a paper or scrambles
    arm order can't be diffed against a recorded baseline for regressions."""
    truths = [
        _gt("paperA", _entry(1, "gaseous exchange")),
        _gt("paperB", _entry(1, "ohm's law")),
    ]
    arms = [
        (
            "base",
            {
                "paperA": {"questions": [_mcq("gaseous exchange in a leaf")]},
                "paperB": {"questions": [_mcq("state ohm's law")]},
            },
        ),
        (
            "variant",
            {
                "paperA": {"questions": [_mcq("gaseous exchange in a leaf")]},
                "paperB": {"questions": [_mcq("state ohm's law")]},
            },
        ),
    ]

    rows = build_rows(truths, arms)

    assert [(r["paper"], r["arm"]) for r in rows] == [
        ("paperA", "base"),
        ("paperA", "variant"),
        ("paperB", "base"),
        ("paperB", "variant"),
    ]
    assert all(r["recall"] == 1.0 for r in rows)


def test_ab_arms_score_independently():
    """Each arm is scored against the same manifest on its own extraction.

    Why this matters: the whole point of the A/B harness is that a worse variant
    shows a worse number — the arms must not share or average results (Rule 7)."""
    truths = [_gt("paperA", _entry(1, "gaseous exchange"), _entry(2, "ohm's law"))]
    arms = [
        (
            "good",
            {
                "paperA": {
                    "questions": [
                        _mcq("gaseous exchange in a leaf"),
                        _mcq("state ohm's law"),
                    ]
                }
            },
        ),
        ("bad", {"paperA": {"questions": [_mcq("gaseous exchange in a leaf")]}}),
    ]

    rows = build_rows(truths, arms)
    by_arm = {r["arm"]: r for r in rows}

    assert by_arm["good"]["recall"] == 1.0
    assert by_arm["bad"]["recall"] == 0.5
    assert by_arm["bad"]["missed_nums"] == [2]


def test_missing_extraction_is_a_loud_row_not_a_zero():
    """An arm with no extraction for a paper yields a missing row, not recall=0.

    Why this matters: a forgotten extraction run must be distinguishable from a
    run that genuinely found nothing — conflating them hides operator error."""
    truths = [_gt("paperA", _entry(1, "gaseous exchange"))]
    arms = [("incomplete", {"paperA": None})]

    rows = build_rows(truths, arms)

    assert rows[0]["missing"] is True
    assert "recall" not in rows[0]
    assert "no extraction found" in format_table(rows)
