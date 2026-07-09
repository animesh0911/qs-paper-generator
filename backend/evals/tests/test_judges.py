"""Judge plumbing: rubric versioning, prompt assembly, verdict parsing."""

import pytest

from evals.judges.base import (
    JudgeRequest,
    build_judge_prompt,
    load_rubric,
    parse_verdict,
)


@pytest.mark.parametrize("rubric", ["generation", "extraction_fidelity", "answers"])
def test_rubrics_load_with_versions(rubric):
    text, version = load_rubric(rubric)
    assert text
    assert version == "v1"


def test_prompt_marks_context_as_ground_truth():
    request = JudgeRequest(
        rubric_name="answers",
        payload={"generated_answer": "CO2"},
        context="NCERT says...",
        context_kind="ncert_excerpts",
    )
    text, _ = load_rubric("answers")
    prompt = build_judge_prompt(request, text)
    assert "ncert_excerpts" in prompt
    assert "treat this as ground truth" in prompt.lower()
    assert '"scores"' in prompt


def test_parse_verdict_extracts_json_from_noise():
    raw = (
        "Here is my grading.\n"
        '{"scores": {"correctness": 4, "groundedness": 2.5}, '
        '"flags": ["unsupported_claim"], "rationale": "Partly supported."}\n'
        "Done."
    )
    verdict = parse_verdict(raw, judge_id="test", rubric_version="v1")
    assert verdict.ok
    assert verdict.scores == {"correctness": 4.0, "groundedness": 2.5}
    assert verdict.flags == ["unsupported_claim"]


def test_parse_verdict_without_scores_fails_closed():
    verdict = parse_verdict("no json here", judge_id="test", rubric_version="v1")
    assert not verdict.ok
    assert verdict.scores == {}
