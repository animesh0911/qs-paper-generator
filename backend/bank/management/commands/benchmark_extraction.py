"""benchmark_extraction — score many extractions across variants into one table.

The repeatable, deterministic (no-LLM) benchmark on top of ``score_extraction``.
Where ``score_extraction`` grades one extraction against one manifest, this
command grades a whole directory of ground-truth manifests against one or more
*arms* — named directories of ``extract_paper`` outputs, one per prompt/model
variant — and prints a single comparison table. That is the A/B harness: each
arm is a prior paid extraction run, the scoring here is free.

An arm is ``name=dir``. For each manifest ``content/eval/<paper>.truth.json`` the
runner looks for ``<dir>/<paper>.json`` (``<paper>`` is the stem of the
manifest's ``source_pdf``) in every arm, scores it, and emits one row per
(paper, arm). ``--record`` writes the rows to JSON so a committed baseline can be
diffed against a later run to catch regressions.

Usage::

    # one arm, every manifest in content/eval → one table
    python manage.py benchmark_extraction content/eval \\
        --arm baseline=/content/parsed

    # A/B two variants, record the numbers for regression tracking
    python manage.py benchmark_extraction content/eval \\
        --arm thinking_on=/content/parsed/thinking_on \\
        --arm thinking_off=/content/parsed/thinking_off \\
        --record content/eval/results/2026-06-04.json

Producing the per-arm extractions is a paid, consent-gated step (CLAUDE.md
Rule 13); this command never calls an LLM.
"""

from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from bank.management.commands.score_extraction import score

_METRIC_KEYS = (
    "expected",
    "extracted",
    "matched",
    "recall",
    "precision",
    "section_accuracy",
    "qtype_accuracy",
    "structure_usable",
)


def build_rows(
    truths: list[tuple[str, dict]],
    arms: list[tuple[str, dict[str, dict | None]]],
) -> list[dict]:
    """Score every (paper, arm) pair into a flat list of rows. Pure — no I/O.

    ``truths`` is ``[(paper, ground_truth), ...]``; ``arms`` is
    ``[(arm_name, {paper: extraction | None}), ...]`` where a ``None`` (or
    missing key) means that arm has no extraction for that paper — recorded as a
    ``missing`` row rather than scored, so an absent run is loud, not a silent
    zero (Rule 12). Rows are ordered paper-major, arm-minor for a stable table.
    """
    rows: list[dict] = []
    for paper, gt in truths:
        for arm_name, by_paper in arms:
            extraction = by_paper.get(paper)
            if extraction is None:
                rows.append({"paper": paper, "arm": arm_name, "missing": True})
                continue
            result = score(extraction, gt)
            row = {"paper": paper, "arm": arm_name, "missing": False}
            row.update({k: result[k] for k in _METRIC_KEYS})
            row["missed_nums"] = [m.get("num") for m in result["missed"]]
            row["spurious"] = len(result["spurious"])
            rows.append(row)
    return rows


def format_table(rows: list[dict]) -> str:
    """Render rows as a fixed-width text table, missing arms flagged inline."""
    header = (
        f"{'paper':<22} {'arm':<16} {'exp':>4} {'ext':>4} {'mat':>4} "
        f"{'rec':>5} {'prec':>5} {'sect':>5} {'qtyp':>5} {'struct':>6}  missed/spurious"
    )
    lines = [header, "-" * len(header)]
    for r in rows:
        if r.get("missing"):
            lines.append(f"{r['paper']:<22} {r['arm']:<16} — no extraction found —")
            continue
        missed = ",".join(str(n) for n in r["missed_nums"]) or "-"
        lines.append(
            f"{r['paper']:<22} {r['arm']:<16} "
            f"{r['expected']:>4} {r['extracted']:>4} {r['matched']:>4} "
            f"{r['recall']:>5.2f} {r['precision']:>5.2f} "
            f"{r['section_accuracy']:>5.2f} {r['qtype_accuracy']:>5.2f} "
            f"{r['structure_usable']:>6.2f}  missed[{missed}] spur={r['spurious']}"
        )
    return "\n".join(lines)


class Command(BaseCommand):
    help = "Score a directory of manifests across one or more arms (no LLM)."

    def add_arguments(self, parser):
        parser.add_argument(
            "truth_dir",
            type=str,
            help="Directory of *.truth.json manifests, e.g. content/eval.",
        )
        parser.add_argument(
            "--arm",
            action="append",
            default=[],
            metavar="name=dir",
            dest="arms",
            help="A variant's extraction dir, e.g. baseline=/content/parsed. "
            "Repeatable; ≥2 arms is an A/B.",
        )
        parser.add_argument(
            "--record",
            type=str,
            default=None,
            help="Write the scored rows to this JSON path for regression tracking.",
        )

    def handle(self, *args, **options):
        truth_dir = Path(options["truth_dir"])
        if not truth_dir.is_dir():
            raise CommandError(f"Not a directory: {truth_dir}")
        if not options["arms"]:
            raise CommandError("Pass at least one --arm name=dir.")

        manifests = sorted(truth_dir.glob("*.truth.json"))
        if not manifests:
            raise CommandError(f"No *.truth.json manifests in {truth_dir}.")

        truths: list[tuple[str, dict]] = []
        for path in manifests:
            gt = json.loads(path.read_text())
            paper = Path(gt["source_pdf"]).stem
            truths.append((paper, gt))

        arms: list[tuple[str, dict[str, dict | None]]] = []
        for spec in options["arms"]:
            name, sep, dir_str = spec.partition("=")
            if not sep or not name or not dir_str:
                raise CommandError(f"--arm must be name=dir, got: {spec!r}")
            arm_dir = Path(dir_str)
            if not arm_dir.is_dir():
                raise CommandError(f"Arm {name!r} dir is not a directory: {arm_dir}")
            by_paper: dict[str, dict | None] = {}
            for paper, _gt in truths:
                ext_path = arm_dir / f"{paper}.json"
                by_paper[paper] = (
                    json.loads(ext_path.read_text()) if ext_path.is_file() else None
                )
            arms.append((name, by_paper))

        rows = build_rows(truths, arms)
        self.stdout.write(format_table(rows))

        if options["record"]:
            record_path = Path(options["record"])
            record_path.parent.mkdir(parents=True, exist_ok=True)
            record_path.write_text(json.dumps(rows, indent=2) + "\n")
            self.stdout.write(
                self.style.SUCCESS(f"Recorded {len(rows)} rows to {record_path}.")
            )
