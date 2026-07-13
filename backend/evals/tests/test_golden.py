"""Golden sets: draft/verify lifecycle and validation."""

import json

import pytest

from evals.datasets.loaders import DatasetError
from evals.golden import draft_golden_set, load_golden_sets, spread_indices

RECORD = {"scenario": "generation", "run_id": "run1", "model_eval_id": "m"}


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


def test_spread_indices_samples_across_the_whole_list():
    assert spread_indices(2, 5) == [0, 1]
    indices = spread_indices(30, 3)
    assert len(indices) == 3
    assert indices[0] == 0
    assert indices[-1] >= 20
