"""Eval CLI — the entrypoint agents (Claude Code / Codex) and humans drive.

Run inside the web container (host Python cannot run Django 5.1)::

    docker compose exec web python -m evals.run <command> ...

Commands:

- ``generation | extraction | answers`` — the paid phase for one scenario.
  **Dry-run by default**: prints the unit matrix + cost forecast and exits.
  Add ``--yes`` to consent to API spend (subject to ``--max-usd``).
- ``score`` — deterministic metrics for stored records (free, no LLM).
- ``deepeval-score`` — the one judged scoring path: decomposed metrics +
  golden agreement (judge billing is consent-gated with ``--yes``).
- ``list-models`` — the registry with pricing status (what still needs
  verification before it can be run priced).

Every command exits 0 on success, 1 on a refused/failed run, and prints
one-line-parseable paths of everything it wrote — the harness contract for
agents is in evals/README.md.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from evals.bootstrap import ensure_django


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    ensure_django()
    try:
        return args.func(args)
    except Exception as exc:  # noqa: BLE001 — CLI boundary: fail loud, exit 1
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


def _build_parser() -> argparse.ArgumentParser:
    from evals.registry import MODELS

    parser = argparse.ArgumentParser(prog="evals.run", description=__doc__)
    sub = parser.add_subparsers(required=True)
    default_models = ["google/gemini-3.5-flash", "deepseek-v4-flash"]

    def add_common(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--models",
            type=_csv,
            default=default_models,
            help=f"CSV of model eval ids (known: {', '.join(sorted(MODELS))})",
        )
        p.add_argument("--trials", type=int, default=3)
        p.add_argument(
            "--yes",
            action="store_true",
            help="Consent to paid LLM API calls (without this: dry-run).",
        )
        p.add_argument("--max-usd", type=float, default=None)
        p.add_argument("--allow-unverified-pricing", action="store_true")
        p.add_argument("--out", type=Path, default=None, help="RunRecord JSONL path.")

    p_gen = sub.add_parser("generation", help="Scenario 1: bulk Q&A generation.")
    add_common(p_gen)
    p_gen.add_argument("--batch-sizes", type=_csv_int, default=[30, 15])
    p_gen.add_argument("--fixtures", type=_csv, default=None)
    p_gen.set_defaults(func=_cmd_run, scenario="generation")

    p_ext = sub.add_parser("extraction", help="Scenario 2: PDF extraction.")
    add_common(p_ext)
    p_ext.add_argument(
        "--arms",
        type=_csv,
        default=["native_pdf", "ocr_mistral", "docling_guardrail"],
    )
    p_ext.add_argument(
        "--datasets",
        type=_csv,
        default=["paper:31_1_1_Science"],
        help="CSV of paper:<stem> and/or bundle:<pages> (e.g. bundle:50).",
    )
    p_ext.set_defaults(func=_cmd_run, scenario="extraction")

    p_ans = sub.add_parser("answers", help="Scenario 3: answers for extraction.")
    add_common(p_ans)
    p_ans.add_argument("--ingestion-job", type=int, default=None)
    p_ans.add_argument("--question-limit", type=int, default=250)
    p_ans.add_argument("--chunk-sizes", type=_csv_int, default=[25])
    p_ans.set_defaults(func=_cmd_run, scenario="answers")

    p_score = sub.add_parser(
        "score",
        help="Deterministic metrics for stored records (judged: deepeval-score).",
    )
    p_score.add_argument("--records", type=Path, required=True)
    p_score.add_argument("--out", type=Path, default=None)
    p_score.set_defaults(func=_cmd_score)

    p_draft = sub.add_parser(
        "draft-goldens",
        help="Draft golden files from stored runs for human verification.",
    )
    p_draft.add_argument("--records", type=Path, required=True)
    p_draft.add_argument("--sample", type=int, default=12)
    p_draft.set_defaults(func=_cmd_draft_goldens)

    p_deep = sub.add_parser(
        "deepeval-score",
        help="Score stored generation runs with the deepeval metric suite.",
    )
    p_deep.add_argument("--records", type=Path, required=True)
    p_deep.add_argument("--judge-model", default="google/gemini-3.5-flash")
    p_deep.add_argument(
        "--sample",
        type=int,
        default=5,
        help="Questions per record (0 = all; golden items win when present).",
    )
    p_deep.add_argument("--out-dir", type=Path, default=None)
    p_deep.add_argument("--max-concurrent", type=int, default=8)
    p_deep.add_argument(
        "--metrics",
        type=_csv,
        default=None,
        help="Bare metric names to run (tuning loop); default: full suite.",
    )
    p_deep.add_argument(
        "--use-cache",
        action="store_true",
        help="Reuse deepeval's disk cache; unchanged cases cost no judge calls.",
    )
    p_deep.add_argument(
        "--yes",
        action="store_true",
        help="Consent to paid judge LLM calls (without this: dry-run).",
    )
    p_deep.set_defaults(func=_cmd_deepeval_score)

    p_list = sub.add_parser("list-models", help="Registry + pricing status.")
    p_list.set_defaults(func=_cmd_list_models)
    return parser


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _csv_int(value: str) -> list[int]:
    return [int(item) for item in _csv(value)]


def _scenario_module(name: str):
    from evals.scenarios import answers, extraction, generation

    return {"generation": generation, "extraction": extraction, "answers": answers}[
        name
    ]


def _cmd_run(args: argparse.Namespace) -> int:
    from evals.budget import BudgetGate, estimate_units_usd, max_run_usd
    from evals.datasets import RESULTS_DIR
    from evals.records import append_records
    from evals.registry import get_model

    module = _scenario_module(args.scenario)
    units = module.build_units(args)
    if not units:
        print("Empty unit matrix — nothing to do.")
        return 1

    # Forecast per model (docling_guardrail rows carry the pseudo-model "none").
    estimates: dict[str, float | None] = {}
    for model_id in sorted({u.model_eval_id for u in units}):
        model_units = [module.estimate(u) for u in units if u.model_eval_id == model_id]
        if model_id == "none":
            estimates[model_id] = 0.0
            continue
        estimates[model_id] = estimate_units_usd(get_model(model_id), model_units)

    print(f"{args.scenario}: {len(units)} units")
    for unit in units:
        print(f"  {unit.label}")
    for model_id, forecast in estimates.items():
        shown = (
            "unpriced (verify registry)" if forecast is None else f"~${forecast:.3f}"
        )
        print(f"forecast {model_id}: {shown}")

    if not args.yes:
        print("\nDRY RUN (no API calls made). Re-run with --yes to execute.")
        return 0

    gate = BudgetGate(
        cap_usd=max_run_usd(args.max_usd),
        yes=args.yes,
        allow_unverified_pricing=args.allow_unverified_pricing,
    )
    gate.authorise(estimates)

    out = args.out or (
        RESULTS_DIR
        / f"{args.scenario}-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}.jsonl"
    )
    completed = failed = 0
    for unit in units:
        # A failed cell is a result, not a run-abort: matrix runs cover
        # models that flake on structured output (2026-07-13: gpt-oss-120b
        # emitted unparseable JSON and killed the remaining 8 cells), and
        # the record schema + report already carry success/error per row.
        # Budget-gate refusals must still abort, so they re-raise.
        try:
            record = module.run_unit(unit)
        except Exception as exc:  # noqa: BLE001 — recorded, not swallowed
            if "budget" in type(exc).__name__.lower():
                raise
            record = _failure_record(unit, exc)
            failed += 1
            print(f"FAILED {unit.label}: {record.error}")
        else:
            completed += 1
            cost = "n/a" if record.cost_usd is None else f"${record.cost_usd:.4f}"
            print(f"done {unit.label}: cost={cost} wall={record.wall_ms}ms")
        append_records(out, [record])
        gate.charge(record.cost_usd)

    print(f"\nwrote {completed + failed} records ({failed} failed) -> {out}")
    print(f"next: python -m evals.run score --records {out}")
    return 0


def _failure_record(unit, exc: Exception):
    """A success=False RunRecord for a unit whose production call raised."""
    from evals.records import RunRecord
    from evals.registry import MODELS

    spec = MODELS.get(unit.model_eval_id)
    return RunRecord(
        scenario=unit.scenario,
        arm=unit.arm,
        model_eval_id=unit.model_eval_id,
        provider=spec.provider if spec else "",
        model=spec.model if spec else unit.model_eval_id,
        config={**unit.config, "trial": unit.trial},
        pricing_verified=spec.pricing_verified if spec else False,
        success=False,
        error=f"{type(exc).__name__}: {exc}",
    )


def _cmd_score(args: argparse.Namespace) -> int:
    # Deterministic-only by design: there is exactly ONE judged scoring path
    # (deepeval-score), so "which number is the number" never has two answers.
    from evals.records import read_records

    rows = read_records(args.records)
    out = args.out or args.records.with_suffix(".scored.jsonl")
    scored = 0
    with out.open("w", encoding="utf-8") as fh:
        for row in rows:
            # Failure records have no artifact to score; they pass through so
            # the report still counts them against the model.
            if row.get("success"):
                module = _scenario_module(row["scenario"])
                row["accuracy"] = module.score_unit(row)
                scored += 1
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    print(f"scored {scored} records -> {out}")
    print(
        "judged metrics + golden agreement: python -m evals.run deepeval-score "
        f"--records {args.records}"
    )
    print(f"next: python -m evals.report --records {out}")
    return 0


def _cmd_draft_goldens(args: argparse.Namespace) -> int:
    from evals.golden import RUBRIC_DIMENSIONS, draft_golden_set
    from evals.records import read_records

    drafted = 0
    for row in read_records(args.records):
        scenario = row["scenario"]
        if scenario not in RUBRIC_DIMENSIONS:
            print(f"skip {row.get('run_id')}: no golden lane for {scenario!r}")
            continue
        module = _scenario_module(scenario)
        items = module.golden_items(row, args.sample)
        if not items:
            print(f"skip {row.get('run_id')}: artifact has no gradable items")
            continue
        path = draft_golden_set(row, items)
        drafted += 1
        print(f"drafted {path}")
    if not drafted:
        print("ERROR: no golden drafts written.", file=sys.stderr)
        return 1
    print(
        "Human next: fill every human_scores dimension (0-5, -1 = n/a), "
        "set verified_by + verified_at, and commit the file."
    )
    return 0


def _cmd_deepeval_score(args: argparse.Namespace) -> int:
    from evals.deepeval_suite.runner import (
        plan_generation_suite,
        score_generation_records,
    )

    plan = plan_generation_suite(
        args.records, args.sample, args.judge_model, args.metrics
    )
    est = "unpriced" if plan.est_judge_usd is None else f"~${plan.est_judge_usd:.2f}"
    selected = f" metrics={','.join(args.metrics)};" if args.metrics else ""
    print(
        f"deepeval suite: {plan.cases} test cases from {plan.records} records;"
        f"{selected} judge {plan.judge_model}, "
        f"~{plan.est_judge_calls} judge calls, {est}"
    )
    if not args.yes:
        print("\nDRY RUN (no judge calls made). Re-run with --yes to execute.")
        return 0

    result = score_generation_records(
        args.records,
        judge_model=args.judge_model,
        sample=args.sample,
        out_dir=args.out_dir,
        max_concurrent=args.max_concurrent,
        metrics_filter=args.metrics,
        use_cache=args.use_cache,
    )
    print(f"\nscored {result.cases} cases -> {result.results_folder}")
    print(f"{'metric':<26} {'mean':>6} {'pass':>6}")
    for name, mean in result.metric_means.items():
        print(f"{name:<26} {mean:>6.2f} {result.metric_pass_rates.get(name, 0):>6.0%}")
    if result.agreement:
        print("\njudge-human agreement (0-5 scale, vs verified goldens)")
        for name, stats in result.agreement.items():
            print(
                f"{name:<26} n={stats['n']} mad={stats['mean_abs_diff']:.2f} "
                f"within_1={stats['within_1']:.0%}"
            )
    if result.failures:
        print(f"\n{len(result.failures)} metric executions errored (ignored):")
        for failure in result.failures[:10]:
            print(f"  {failure}")
    spend = result.judge_cost_usd
    print(f"\njudge spend: {'unpriced' if spend is None else f'${spend:.4f}'}")
    return 0


def _cmd_list_models(args: argparse.Namespace) -> int:
    from evals.registry import MODELS, OCR_ENGINES

    print(f"{'eval id':<32} {'provider':<12} {'model':<28} pricing")
    for spec in MODELS.values():
        pricing = (
            f"${spec.usd_per_1m_input}/{spec.usd_per_1m_output} per 1M"
            if spec.pricing_verified
            else "UNVERIFIED — fill evals/registry.py"
        )
        print(f"{spec.eval_id:<32} {spec.provider:<12} {spec.model:<28} {pricing}")
    for ocr in OCR_ENGINES.values():
        pricing = f"${ocr.usd_per_page}/page" if ocr.pricing_verified else "UNVERIFIED"
        print(f"{ocr.eval_id:<32} {'ocr':<12} {'':<28} {pricing}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
