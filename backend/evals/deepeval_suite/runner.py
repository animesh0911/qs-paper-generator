"""Run the deepeval suite over stored generation records.

One ``evaluate()`` call per stored record, so deepeval's per-run
``hyperparameters`` (candidate model, batch size, fixture) are exact and the
local ``TestRun`` JSONs under ``results_folder`` become the experiment
history. Sampling defaults to the verified golden items for a run, which
keeps judge spend bounded and makes deepeval scores directly comparable with
the human grades.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from evals.datasets import EVAL_ROOT
from evals.deepeval_suite.adapter import generation_test_cases
from evals.deepeval_suite.judge import SeamJudgeLLM
from evals.deepeval_suite.metrics import build_generation_metrics
from evals.golden import load_golden_sets, spread_indices
from evals.records import read_records
from evals.registry import cost_usd, get_model

DEEPEVAL_RUNS_DIR = EVAL_ROOT / "deepeval-runs"

# The four judge dimensions shared with the golden rubric (0-5 human scale vs
# deepeval's 0-1); question_shape covers qtype_conformity deterministically.
_AGREEMENT_DIMS = (
    "ncert_fidelity",
    "self_containedness",
    "answer_correctness",
    "difficulty_plausibility",
)
# Judge-call priors per metric (G-Evals are one call, Faithfulness ~3; code
# metrics are free) with per-call tokens trued to the 2026-07-13 suite run
# ($0.25 actual vs $0.73 forecast on the old 2k/250 priors — G-Eval prompts
# are short: steps + rendered question + a small cited excerpt).
_LLM_CALLS_BY_METRIC = {
    "ncert_fidelity": 1,
    "self_containedness": 1,
    "answer_correctness": 1,
    "difficulty_plausibility": 1,
    "Faithfulness": 3,
}
_EST_INPUT_TOKENS_PER_CALL = 900
_EST_OUTPUT_TOKENS_PER_CALL = 120


@dataclass
class SuitePlan:
    records: int
    cases: int
    judge_model: str
    est_judge_calls: int
    est_judge_usd: float | None


@dataclass
class SuiteResult:
    cases: int
    metric_means: dict[str, float]
    metric_pass_rates: dict[str, float]
    agreement: dict[str, dict[str, float]]
    judge_cost_usd: float | None
    results_folder: str
    failures: list[str] = field(default_factory=list)


def plan_generation_suite(
    records_path: Path,
    sample: int,
    judge_model: str,
    metrics_filter: list[str] | None = None,
):
    """Dry-run forecast: what would run and roughly what the judge bills."""
    rows = _generation_rows(records_path)
    cases = sum(len(_case_indices(row, sample)) for row in rows)
    calls_per_case = sum(
        calls
        for name, calls in _LLM_CALLS_BY_METRIC.items()
        if not metrics_filter or name in metrics_filter
    )
    calls = cases * calls_per_case
    spec = get_model(judge_model)
    est = cost_usd(
        spec,
        input_tokens=calls * _EST_INPUT_TOKENS_PER_CALL,
        output_tokens=calls * _EST_OUTPUT_TOKENS_PER_CALL,
    )
    return SuitePlan(
        records=len(rows),
        cases=cases,
        judge_model=judge_model,
        est_judge_calls=calls,
        est_judge_usd=est,
    )


def score_generation_records(
    records_path: Path,
    *,
    judge_model: str,
    sample: int = 5,
    out_dir: Path | None = None,
    max_concurrent: int = 8,
    metrics_filter: list[str] | None = None,
    use_cache: bool = False,
) -> SuiteResult:
    """Score sampled questions from every generation record in a JSONL.

    ``metrics_filter`` (bare metric names) exists for the tuning loop: one
    metric over the golden sample costs cents, so a criteria change can be
    validated against human grades without re-billing the whole suite.
    ``use_cache`` reads deepeval's disk cache (written on every run), so
    unchanged case+metric pairs cost zero judge calls — the regression gate
    relies on this.
    """
    from deepeval import evaluate
    from deepeval.evaluate import (
        AsyncConfig,
        CacheConfig,
        DisplayConfig,
        ErrorConfig,
    )

    rows = _generation_rows(records_path)
    out_dir = out_dir or (DEEPEVAL_RUNS_DIR / records_path.stem)
    out_dir.mkdir(parents=True, exist_ok=True)

    judge = SeamJudgeLLM(judge_model)
    scores: dict[str, list[float]] = {}
    passes: dict[str, list[bool]] = {}
    agreement_pairs: dict[str, list[tuple[float, float]]] = {}
    failures: list[str] = []
    total_cases = 0

    for row in rows:
        indices = _case_indices(row, sample)
        cases = generation_test_cases(row, indices)
        if not cases:
            continue
        human_by_index = _human_scores_by_index(row)
        total_cases += len(cases)
        result = evaluate(
            test_cases=cases,
            metrics=_filter_metrics(build_generation_metrics(judge), metrics_filter),
            hyperparameters={
                "candidate_model": row.get("model_eval_id"),
                "batch_size": row.get("batch_size"),
                "fixture_id": (row.get("config") or {}).get("fixture_id"),
                "judge": judge.get_model_name(),
            },
            async_config=AsyncConfig(max_concurrent=max_concurrent),
            cache_config=CacheConfig(use_cache=use_cache),
            error_config=ErrorConfig(ignore_errors=True),
            display_config=DisplayConfig(
                results_folder=str(out_dir),
                print_results=False,
                show_indicator=False,
                inspect_after_run=False,
            ),
        )
        for test_result in getattr(result, "test_results", []) or []:
            index = _case_index(test_result)
            for metric in getattr(test_result, "metrics_data", []) or []:
                # deepeval displays G-Eval metrics as "<name> [GEval]"; the
                # bare name is the rubric dimension goldens are keyed by.
                name = str(getattr(metric, "name", "")).split(" [")[0]
                score = getattr(metric, "score", None)
                error = getattr(metric, "error", None)
                if error:
                    failures.append(f"{getattr(test_result, 'name', '?')}/{name}")
                    continue
                if score is None:
                    continue
                scores.setdefault(name, []).append(float(score))
                passes.setdefault(name, []).append(
                    bool(getattr(metric, "success", False))
                )
                human = (human_by_index.get(index) or {}).get(name)
                if name in _AGREEMENT_DIMS and human is not None and human >= 0:
                    agreement_pairs.setdefault(name, []).append(
                        (float(score) * 5, float(human))
                    )

    return SuiteResult(
        cases=total_cases,
        metric_means={n: sum(v) / len(v) for n, v in sorted(scores.items())},
        metric_pass_rates={n: sum(v) / len(v) for n, v in sorted(passes.items())},
        agreement={
            name: {
                "n": len(pairs),
                "mean_abs_diff": sum(abs(j - h) for j, h in pairs) / len(pairs),
                "within_1": sum(1 for j, h in pairs if abs(j - h) <= 1) / len(pairs),
            }
            for name, pairs in sorted(agreement_pairs.items())
        },
        judge_cost_usd=judge.cost_usd,
        results_folder=str(out_dir),
        failures=failures,
    )


def _filter_metrics(metrics: list, wanted: list[str] | None) -> list:
    if not wanted:
        return metrics
    kept = [m for m in metrics if _bare_metric_name(m) in set(wanted)]
    if not kept:
        known = ", ".join(_bare_metric_name(m) for m in metrics)
        raise ValueError(f"--metrics matched nothing; known metrics: {known}")
    return kept


def _bare_metric_name(metric: Any) -> str:
    return str(getattr(metric, "name", "") or getattr(metric, "__name__", ""))


def _generation_rows(records_path: Path) -> list[dict[str, Any]]:
    # Failure records (success=False) have no artifact to build cases from;
    # they stay in the JSONL for the report's failure counts but are not
    # scoreable.
    rows = [
        r
        for r in read_records(records_path)
        if r.get("scenario") == "generation" and r.get("success")
    ]
    if not rows:
        raise ValueError(f"No successful generation records in {records_path}.")
    return rows


def _case_indices(row: dict[str, Any], sample: int) -> list[int]:
    """Golden item indices when a verified set exists; else an even spread."""
    goldens, _ = load_golden_sets("generation", str(row.get("run_id") or ""))
    indices = sorted(
        int(item.key.split(":", 1)[1])
        for golden_set in goldens
        for item in golden_set.items
        if item.key.startswith("i:")
    )
    if indices:
        return indices[:sample] if sample else indices
    total = int(row.get("delivered") or 0)
    return spread_indices(total, sample) if sample else list(range(total))


def _human_scores_by_index(row: dict[str, Any]) -> dict[int, dict[str, float]]:
    goldens, _ = load_golden_sets("generation", str(row.get("run_id") or ""))
    return {
        int(item.key.split(":", 1)[1]): item.human_scores
        for golden_set in goldens
        for item in golden_set.items
        if item.key.startswith("i:")
    }


def _case_index(test_result: Any) -> int:
    name = str(getattr(test_result, "name", "") or "")
    _, _, suffix = name.rpartition(":i")
    return int(suffix) if suffix.isdigit() else -1
