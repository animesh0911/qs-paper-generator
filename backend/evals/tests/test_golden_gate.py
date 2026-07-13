"""The #225 regression gate over the verified golden dataset.

Two layers, two costs:

- **Deterministic layer** (always runs, free): production's structural and
  lexical-citation metrics over the 20 golden cases, compared per-case to a
  frozen baseline. A diff here means eval adapter/metric code or committed
  data changed grounding behaviour — deliberate changes update the baseline
  in the same commit.
- **Judged layer** (skipped unless ``EVALS_GOLDEN_GATE=1``): the G-Eval
  dimensions + Faithfulness over the same cases, asserting judge–human
  agreement stays within #225's calibrated targets (mad ≤ 0.75, within-1 ≥
  80% per dimension — chosen as the issue's uniform target with headroom
  over the 2026-07-13 measurements of 0.10–0.53 mad). The env var is the
  Rule-13 consent: the first fill bills ~$0.20 through the seam judge;
  deepeval's disk cache makes unchanged re-runs free (verified: second run
  reports $0 judge spend).

Run the judged gate::

    docker compose exec -e EVALS_GOLDEN_GATE=1 web \
        pytest evals/tests/test_golden_gate.py -q
"""

import os
from pathlib import Path

import pytest

from evals.deepeval_suite.adapter import generation_test_cases
from evals.deepeval_suite.metrics import CitationSupportMetric, QuestionShapeMetric
from evals.deepeval_suite.runner import _case_indices, _generation_rows

RECORDS = Path("/content/eval/results/generation-20260710-134623.jsonl")

AGREEMENT_DIMS = (
    "ncert_fidelity",
    "self_containedness",
    "answer_correctness",
    "difficulty_plausibility",
)
AGREEMENT_MAD_MAX = 0.75
AGREEMENT_WITHIN_1_MIN = 0.80
FAITHFULNESS_PASS_RATE_MIN = 0.90  # measured 1.00 on 2026-07-13

# (question_shape, citation_support) per golden case, frozen 2026-07-13.
# The three sub-1.0 citation rows are the known lexical/judge disagreement
# items (restated answers, the lubricant premise, the wrong-excerpt cite).
DETERMINISTIC_BASELINE = {
    "0b9c0ff4bf85:i0": (1.0, 1.0),
    "0b9c0ff4bf85:i6": (1.0, 1.0),
    "0b9c0ff4bf85:i12": (1.0, 1.0),
    "0b9c0ff4bf85:i18": (1.0, 1.0),
    "0b9c0ff4bf85:i24": (1.0, 0.5),
    "f0142df4a5a2:i0": (1.0, 1.0),
    "f0142df4a5a2:i3": (1.0, 1.0),
    "f0142df4a5a2:i6": (1.0, 1.0),
    "f0142df4a5a2:i9": (1.0, 1.0),
    "f0142df4a5a2:i12": (1.0, 1.0),
    "c912883ffcc8:i0": (1.0, 1.0),
    "c912883ffcc8:i6": (1.0, 1.0),
    "c912883ffcc8:i12": (1.0, 0.5),
    "c912883ffcc8:i18": (1.0, 1.0),
    "c912883ffcc8:i24": (1.0, 1.0),
    "783c21416f02:i0": (1.0, 1.0),
    "783c21416f02:i3": (1.0, 1.0),
    "783c21416f02:i6": (1.0, 1.0),
    "783c21416f02:i9": (1.0, 1.0),
    "783c21416f02:i12": (1.0, 0.0),
}

records_required = pytest.mark.skipif(
    not RECORDS.is_file(),
    reason="golden run records not mounted at /content",
)
judged_gate = pytest.mark.skipif(
    os.getenv("EVALS_GOLDEN_GATE") != "1",
    reason=(
        "judged gate bills the seam judge on cache misses; consent with "
        "EVALS_GOLDEN_GATE=1 (unchanged re-runs are cache-served and free)"
    ),
)


def _golden_cases():
    return [
        case
        for row in _generation_rows(RECORDS)
        for case in generation_test_cases(row, _case_indices(row, 0))
    ]


@records_required
def test_deterministic_metrics_match_frozen_baseline():
    shape, cite = QuestionShapeMetric(), CitationSupportMetric()
    observed = {
        case.name: (shape.measure(case), cite.measure(case)) for case in _golden_cases()
    }

    assert observed == DETERMINISTIC_BASELINE, (
        "Deterministic grounding metrics diverged from the frozen baseline. "
        "If the change is deliberate (adapter/screen/data), update "
        "DETERMINISTIC_BASELINE in the same commit; otherwise this is a "
        "regression."
    )


@records_required
@judged_gate
def test_judge_agreement_with_humans_holds_on_goldens():
    from evals.deepeval_suite.runner import score_generation_records

    result = score_generation_records(
        RECORDS,
        judge_model="google/gemini-3.5-flash",
        sample=0,  # all golden items
        out_dir=Path("/content/eval/deepeval-runs/golden-gate"),
        metrics_filter=[*AGREEMENT_DIMS, "Faithfulness"],
        use_cache=True,
    )

    assert result.cases == len(DETERMINISTIC_BASELINE)
    problems = []
    for dim in AGREEMENT_DIMS:
        stats = result.agreement.get(dim)
        if stats is None:
            problems.append(f"{dim}: no agreement pairs computed")
            continue
        if stats["mean_abs_diff"] > AGREEMENT_MAD_MAX:
            problems.append(
                f"{dim}: mad {stats['mean_abs_diff']:.2f} > {AGREEMENT_MAD_MAX}"
            )
        if stats["within_1"] < AGREEMENT_WITHIN_1_MIN:
            problems.append(
                f"{dim}: within_1 {stats['within_1']:.0%} < "
                f"{AGREEMENT_WITHIN_1_MIN:.0%}"
            )
    faithfulness = result.metric_pass_rates.get("Faithfulness")
    if faithfulness is None or faithfulness < FAITHFULNESS_PASS_RATE_MIN:
        problems.append(
            f"Faithfulness pass rate {faithfulness} < {FAITHFULNESS_PASS_RATE_MIN}"
        )

    assert not problems, (
        "Judge drifted from the human-verified goldens:\n  "
        + "\n  ".join(problems)
        + "\nEither the metric/judge change regressed, or the policy moved — "
        "re-verify goldens before touching these thresholds."
    )
