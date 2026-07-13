"""Rubric loading: versioned files stay the judged dimensions' source of truth."""

import pytest

from evals.judges.base import load_rubric


@pytest.mark.parametrize("rubric", ["generation", "extraction_fidelity", "answers"])
def test_rubrics_load_with_versions(rubric):
    text, version = load_rubric(rubric)
    assert text
    assert version == "v1"
