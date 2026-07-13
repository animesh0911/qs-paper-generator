"""Report phase: aggregate run records into comparison tables + monthly cost.

Pure aggregation — no network, no Django models. Costs are **re-priced from
recorded token counts** against the current registry, so verifying a price
after a run retroactively prices those runs correctly; the per-record
``cost_usd`` snapshot is kept only for audit.

Usage::

    python -m evals.run score --records content/eval/results/generation-*.jsonl
    python -m evals.report --records content/eval/results/generation-*.scored.jsonl \
        --usage-profile brief_defaults --out content/eval/results/report.md
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from evals.records import read_records
from evals.registry import MODELS, OCR_ENGINES, cost_usd, to_inr
from evals.stats import summarise


def group_key(row: dict) -> tuple:
    config = {k: v for k, v in (row.get("config") or {}).items() if k != "trial"}
    return (
        row["scenario"],
        row["arm"],
        row["model_eval_id"],
        tuple(sorted(config.items())),
    )


def reprice(row: dict) -> float | None:
    """Current-registry cost for one record: LLM tokens + OCR pages."""
    spec = MODELS.get(row["model_eval_id"])
    llm = (
        cost_usd(
            spec,
            input_tokens=row.get("input_tokens", 0),
            output_tokens=row.get("output_tokens", 0),
            cache_read_tokens=row.get("cache_read_tokens", 0),
        )
        if spec
        else 0.0
    )
    ocr_pages = row.get("ocr_pages", 0)
    ocr = 0.0
    if ocr_pages:
        rate = OCR_ENGINES["mistral-ocr"].usd_per_page
        if rate is None:
            return None  # unpriced OCR poisons the total honestly
        ocr = ocr_pages * rate
    return None if llm is None else llm + ocr


def aggregate(rows: list[dict]) -> list[dict[str, Any]]:
    """One summary dict per (scenario, arm, model, config) group."""
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        groups[group_key(row)].append(row)

    summaries = []
    for key, members in sorted(groups.items()):
        scenario, arm, model_id, config = key
        ok = [m for m in members if m.get("success")]
        costs = [c for c in (reprice(m) for m in ok) if c is not None]
        call_latencies = [
            call["latency_ms"]
            for m in ok
            for call in m.get("calls", [])
            if not call.get("error")
        ]
        summary: dict[str, Any] = {
            "scenario": scenario,
            "arm": arm,
            "model": model_id,
            "config": dict(config),
            "trials": len(members),
            "failed": len(members) - len(ok),
            "batch_size": ok[0].get("batch_size") if ok else 0,
            "delivered_mean": (
                sum(m.get("delivered", 0) for m in ok) / len(ok) if ok else 0.0
            ),
            "cost_usd": summarise(costs) if costs else None,
            "cost_inr_mean": to_inr(sum(costs) / len(costs)) if costs else None,
            "wall_ms": summarise([m.get("wall_ms", 0) for m in ok]) if ok else None,
            "call_latency_ms": summarise(call_latencies) if call_latencies else None,
            "tokens_in_mean": (
                sum(m.get("input_tokens", 0) for m in ok) / len(ok) if ok else 0
            ),
            "tokens_out_mean": (
                sum(m.get("output_tokens", 0) for m in ok) / len(ok) if ok else 0
            ),
            "accuracy": _merge_accuracy([m.get("accuracy") for m in ok]),
        }
        summaries.append(summary)
    return summaries


def _merge_accuracy(accuracies: list[dict | None]) -> dict[str, Any]:
    """Mean the numeric leaves of per-trial accuracy dicts (one level deep
    per scenario convention); non-numeric leaves keep the first value."""
    merged: dict[str, Any] = {}
    present = [a for a in accuracies if a]
    if not present:
        return merged
    for key in {k for a in present for k in a}:
        values = [a[key] for a in present if key in a]
        numeric = [v for v in values if isinstance(v, (int, float))]
        if numeric and len(numeric) == len(values):
            merged[key] = sum(numeric) / len(numeric)
        elif all(isinstance(v, dict) for v in values):
            merged[key] = _merge_accuracy(values)  # type: ignore[arg-type]
        else:
            merged[key] = values[0]
    return merged


# ---------------------------------------------------------------------------
# Per-user monthly cost roll-up
# ---------------------------------------------------------------------------


def monthly_costs(
    summaries: list[dict[str, Any]], profile: dict[str, dict]
) -> list[dict[str, Any]]:
    """Cross measured per-run cost with a usage profile → $/user/month.

    A profile names runs_per_month per scenario (see
    datasets/fixtures/usage_profiles.json). For each measured (scenario,
    model) group whose config matches the profile's driver (batch_size /
    pages / questions), monthly = mean run cost × runs_per_month.
    """
    rows = []
    for summary in summaries:
        scenario = summary["scenario"]
        usage = profile.get(scenario)
        if not usage or not summary["cost_usd"]:
            continue
        if not _matches_profile(summary, usage):
            continue
        monthly_usd = summary["cost_usd"]["mean"] * usage["runs_per_month"]
        rows.append(
            {
                "scenario": scenario,
                "arm": summary["arm"],
                "model": summary["model"],
                "runs_per_month": usage["runs_per_month"],
                "usd_per_run": summary["cost_usd"]["mean"],
                "usd_per_month": monthly_usd,
                "inr_per_month": to_inr(monthly_usd),
            }
        )
    return rows


def _matches_profile(summary: dict, usage: dict) -> bool:
    config = summary.get("config", {})
    if "batch_size" in usage and "batch_size" in config:
        return config["batch_size"] == usage["batch_size"]
    if "pages_per_run" in usage:
        return summary.get("batch_size") == usage["pages_per_run"]
    if "questions_per_run" in usage and "question_limit" in config:
        return config["question_limit"] == usage["questions_per_run"]
    return True  # scenario measured in only one config


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def render_markdown(
    summaries: list[dict[str, Any]],
    monthly: list[dict[str, Any]],
    profile_name: str,
) -> str:
    lines = ["# Eval report", ""]
    for scenario in ("generation", "extraction", "answers"):
        rows = [s for s in summaries if s["scenario"] == scenario]
        if not rows:
            continue
        lines += [f"## {scenario}", ""]
        lines.append(
            "| arm | model | config | trials | $/run mean±std | wall ms p50 | "
            "call ms p95 | tok in/out | accuracy highlights |"
        )
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for s in rows:
            cost = s["cost_usd"]
            cost_cell = f"{cost['mean']:.4f}±{cost['std']:.4f}" if cost else "unpriced"
            wall_p50 = s["wall_ms"]["p50"] if s["wall_ms"] else 0
            call_p95 = s["call_latency_ms"]["p95"] if s["call_latency_ms"] else 0
            config = ",".join(f"{k}={v}" for k, v in s["config"].items())
            lines.append(
                f"| {s['arm']} | {s['model']} | {config} | {s['trials']} "
                f"(fail {s['failed']}) | {cost_cell} | "
                f"{wall_p50:.0f} | {call_p95:.0f} | "
                f"{s['tokens_in_mean']:.0f}/{s['tokens_out_mean']:.0f} | "
                f"{_accuracy_highlights(s['accuracy'])} |"
            )
        lines.append("")

    if monthly:
        lines += [f"## Per-user monthly cost (profile: {profile_name})", ""]
        lines.append("| scenario | arm | model | runs/mo | $/run | $/mo | ₹/mo |")
        lines.append("|---|---|---|---|---|---|---|")
        for row in monthly:
            lines.append(
                f"| {row['scenario']} | {row['arm']} | {row['model']} | "
                f"{row['runs_per_month']} | {row['usd_per_run']:.4f} | "
                f"{row['usd_per_month']:.4f} | {row['inr_per_month']:.2f} |"
            )
        lines.append("")
    return "\n".join(lines)


def _accuracy_highlights(accuracy: dict[str, Any]) -> str:
    if not accuracy:
        return "unscored"
    parts = []
    for key in ("yield", "recall", "precision", "answered_rate", "corpus_coverage"):
        if isinstance(accuracy.get(key), (int, float)):
            parts.append(f"{key}={accuracy[key]:.2f}")
    deterministic = accuracy.get("deterministic") or {}
    for key in ("recall", "precision"):
        if key in deterministic:
            parts.append(f"{key}={deterministic[key]:.2f}")
    support = accuracy.get("citation_support") or {}
    if isinstance(support.get("supported_rate"), (int, float)):
        parts.append(f"cite_support={support['supported_rate']:.2f}")
    judge = accuracy.get("judge") or {}
    for dim, value in (judge.get("mean_scores") or {}).items():
        parts.append(f"{dim}={value:.1f}")
    agreement = accuracy.get("judge_agreement") or {}
    for dim, stats in (agreement.get("dimensions") or {}).items():
        parts.append(f"Δhuman[{dim}]={stats['mean_abs_diff']:.2f}")
    return " ".join(parts) or "unscored"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evals.report", description=__doc__)
    parser.add_argument("--records", type=Path, nargs="+", required=True)
    parser.add_argument("--usage-profile", default="brief_defaults")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    from evals.datasets.loaders import load_usage_profiles

    rows: list[dict] = []
    for path in args.records:
        rows.extend(read_records(path))
    profiles = load_usage_profiles()
    profile = profiles.get(args.usage_profile)
    if profile is None:
        known = [k for k in profiles if not k.startswith("_")]
        print(f"Unknown usage profile; known: {known}", file=sys.stderr)
        return 1

    summaries = aggregate(rows)
    monthly = monthly_costs(summaries, profile)
    markdown = render_markdown(summaries, monthly, args.usage_profile)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(markdown, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(markdown)
    return 0


if __name__ == "__main__":
    sys.exit(main())
