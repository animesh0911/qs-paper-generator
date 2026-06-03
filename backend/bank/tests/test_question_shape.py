"""Tests for bank.question_shape — the single per-qtype structure spec.

The lockstep test is the point: it asserts the hand-written Gemini response
schema covers every QuestionShape's content regions, so the spec and the schema
can't drift the way ADR-0001 stopped the qtype value from drifting.
"""

from __future__ import annotations

from bank.ingestor import _QUESTION_SCHEMA
from bank.question_shape import QUESTION_SHAPES, fallback_regions


def test_response_schema_covers_every_shape_content_region():
    """Every region a QuestionShape declares must exist in the response schema.

    Why this matters: parse_quality, the document fallback, and the model schema
    all describe the same qtype structure. If a shape names a region the schema
    can't emit, the model can never produce a clean row of that type — caught here
    at import time, not at ingest."""
    schema_regions = set(
        _QUESTION_SCHEMA["properties"]["questions"]["items"]["properties"]["content"][
            "properties"
        ]
    )
    for shape in QUESTION_SHAPES.values():
        missing = set(shape.content_regions) - schema_regions
        assert not missing, f"{shape.qtype} declares regions not in schema: {missing}"


def test_fallback_regions_subset_of_content_regions():
    """A fallback never synthesises a region the qtype doesn't legitimately use."""
    for shape in QUESTION_SHAPES.values():
        assert set(shape.fallback_regions) <= set(shape.content_regions)


def test_fallback_regions_unknown_qtype_defaults_to_stem():
    assert fallback_regions("custom") == ("stem",)


def test_mcq_fallback_includes_options():
    assert "options" in fallback_regions("mcq")
