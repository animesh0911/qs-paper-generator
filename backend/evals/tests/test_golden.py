"""Golden sets: draft/verify lifecycle, validation, judge–human agreement."""

import json
from dataclasses import dataclass

import pytest

from evals.datasets.loaders import DatasetError
from evals.golden import (
    draft_golden_set,
    judge_human_agreement,
    load_golden_sets,
    spread_indices,
)
from evals.judges.base import JudgeRequest, JudgeVerdict

RECORD = {"scenario": "generation", "run_id": "run1", "model_eval_id": "m"}


@dataclass
class StaticJudge:
    """Returns the same scores for every payload — agreement math is exact."""

    scores: dict
    judge_id: str = "static"
    rubric_version: str = "v1"

    def judge(self, request: JudgeRequest) -> JudgeVerdict:
        return JudgeVerdict(
            scores=dict(self.scores),
            judge_id=self.judge_id,
            rubric_version=self.rubric_version,
        )


def _draft(tmp_path, items=None):
    items = items or [("i:0", {"raw_text": "Q"}, "excerpt text")]
    return draft_golden_set(RECORD, items, golden_dir=tmp_path)


def _verify(path, scores_by_key):
    raw = json.loads(path.read_text(encoding="utf-8"))
    for item in raw["items"]:
        item["human_scores"] = scores_by_key[item["key"]]
    raw["verified_by"] = "animesh"
    raw["verified_at"] = "2026-07-10"
    path.write_text(json.dumps(raw), encoding="utf-8")


def test_draft_writes_unscored_skeleton_and_counts_as_pending(tmp_path):
    path = _draft(tmp_path)

    raw = json.loads(path.read_text(encoding="utf-8"))
    assert path.name == "generation-run1.golden.json"
    assert raw["rubric_version"] == "v1"
    assert all(v is None for v in raw["items"][0]["human_scores"].values())
    assert set(raw["items"][0]["human_scores"]) == {
        "ncert_fidelity",
        "self_containedness",
        "qtype_conformity",
        "answer_correctness",
        "difficulty_plausibility",
    }

    verified, pending = load_golden_sets("generation", "run1", golden_dir=tmp_path)
    assert verified == []
    assert pending == 1


def test_draft_refuses_to_overwrite_an_existing_golden(tmp_path):
    _draft(tmp_path)

    with pytest.raises(DatasetError, match="refusing to overwrite"):
        _draft(tmp_path)


def test_verified_set_loads_with_parsed_scores(tmp_path):
    path = _draft(tmp_path)
    _verify(
        path,
        {
            "i:0": {
                "ncert_fidelity": 4,
                "self_containedness": 5,
                "qtype_conformity": 5,
                "answer_correctness": 3,
                "difficulty_plausibility": -1,
            }
        },
    )

    [golden_set], pending = load_golden_sets("generation", "run1", golden_dir=tmp_path)

    assert pending == 0
    assert golden_set.verified
    assert golden_set.items[0].human_scores["ncert_fidelity"] == 4.0


def test_verified_set_with_unscored_dimension_is_loud(tmp_path):
    path = _draft(tmp_path)
    _verify(path, {"i:0": {"ncert_fidelity": None}})

    with pytest.raises(DatasetError, match="unscored but the set is marked"):
        load_golden_sets("generation", "run1", golden_dir=tmp_path)


def test_unknown_score_dimension_is_loud(tmp_path):
    path = _draft(tmp_path)
    _verify(path, {"i:0": {"vibes": 5}})

    with pytest.raises(DatasetError, match="unknown dimensions"):
        load_golden_sets("generation", "run1", golden_dir=tmp_path)


def test_agreement_reports_per_dimension_gap_and_skips_na(tmp_path):
    path = _draft(
        tmp_path,
        items=[("i:0", {"raw_text": "Q0"}, "ctx"), ("i:1", {"raw_text": "Q1"}, "")],
    )
    _verify(
        path,
        {
            "i:0": {"ncert_fidelity": 5, "answer_correctness": 3},
            "i:1": {"ncert_fidelity": 4, "answer_correctness": -1},
        },
    )
    judge = StaticJudge(scores={"ncert_fidelity": 4.0, "answer_correctness": 5.0})
    [golden_set], _ = load_golden_sets("generation", "run1", golden_dir=tmp_path)

    agreement = judge_human_agreement(judge, [golden_set])

    assert agreement["n_judged"] == 2
    fidelity = agreement["dimensions"]["ncert_fidelity"]
    assert fidelity == {"n": 2, "mean_abs_diff": 0.5, "within_1": 1.0}
    correctness = agreement["dimensions"]["answer_correctness"]
    assert correctness == {"n": 1, "mean_abs_diff": 2.0, "within_1": 0.0}
    assert agreement["judge_id"] == "static"


def test_agreement_refuses_rubric_version_mismatch(tmp_path):
    path = _draft(tmp_path)
    _verify(path, {"i:0": {"ncert_fidelity": 5}})
    [golden_set], _ = load_golden_sets("generation", "run1", golden_dir=tmp_path)
    judge = StaticJudge(scores={"ncert_fidelity": 5.0}, rubric_version="v2")

    with pytest.raises(DatasetError, match="re-verify the golden set"):
        judge_human_agreement(judge, [golden_set])


def test_spread_indices_samples_across_the_whole_list():
    assert spread_indices(2, 5) == [0, 1]
    indices = spread_indices(30, 3)
    assert len(indices) == 3
    assert indices[0] == 0
    assert indices[-1] >= 20
