"""Golden sets: hand-verified verdicts that calibrate the LLM judge.

A golden set freezes what one human graded — payload, reference context, and
per-dimension scores — for a sample of one stored run's outputs. The deepeval
suite grades the same items and reports the per-dimension gap as judge–human
agreement: the number that says how much a judged groundedness/correctness
score can be trusted (see ``evals.deepeval_suite.runner`` and the golden
regression gate).

Workflow (HITL — an agent drafts, a human verifies):

1. ``python -m evals.run draft-goldens --records <run>.jsonl`` writes
   ``/content/eval/golden/<scenario>-<run_id>.golden.json`` with frozen
   payloads/contexts and *unscored* ``human_scores`` (judge scores are
   deliberately not prefilled — a human anchored on the judge's numbers
   cannot calibrate it).
2. A human fills every ``human_scores`` dimension (0–5 per the rubric,
   ``-1`` for not-applicable), then sets ``verified_by``/``verified_at``.
3. ``deepeval-score`` samples verified golden items by ``run_id`` and
   reports per-dimension judge–human agreement; drafts are never compared.

File format (``golden_version: 1``)::

    {
      "golden_version": 1,
      "scenario": "generation" | "answers",
      "rubric_name": "...", "rubric_version": "v1",   # stamped at draft time
      "run_id": "...", "model_eval_id": "...",
      "verified_by": "", "verified_at": "",            # human fills → verified
      "items": [{"key": "i:0" | "q:<pk>", "payload": {...}, "context": "...",
                 "human_scores": {"<dim>": null|0-5|-1},
                 "human_flags": [], "note": ""}]
    }

Comparability is guarded the same way rubric verdicts are: a golden set
records the rubric version it was graded under, and agreement refuses to
compare across versions rather than silently mixing them.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from evals.datasets import GOLDEN_DIR
from evals.datasets.loaders import DatasetError
from evals.judges.base import load_rubric

GOLDEN_VERSION = 1

# The dimensions a human scores, per scenario — kept explicit (not parsed out
# of the rubric markdown) so a drafted golden always shows the grader every
# dimension the judge will be compared on. Must track rubrics/*.md.
RUBRIC_DIMENSIONS: dict[str, tuple[str, ...]] = {
    "generation": (
        "ncert_fidelity",
        "self_containedness",
        "qtype_conformity",
        "answer_correctness",
        "difficulty_plausibility",
    ),
    "answers": ("correctness", "groundedness", "marks_depth", "scheme_style"),
}
RUBRIC_BY_SCENARIO = {"generation": "generation", "answers": "answers"}


@dataclass(frozen=True)
class GoldenItem:
    """One human-graded payload, frozen with the context the human saw."""

    key: str  # "i:<index>" (generation) | "q:<question_pk>" (answers)
    payload: dict[str, Any]
    context: str
    human_scores: dict[str, float]
    human_flags: tuple[str, ...] = ()


@dataclass(frozen=True)
class GoldenSet:
    path: Path
    scenario: str
    rubric_name: str
    rubric_version: str
    run_id: str
    verified_by: str
    verified_at: str
    items: tuple[GoldenItem, ...]

    @property
    def verified(self) -> bool:
        return bool(self.verified_by and self.verified_at)


def spread_indices(total: int, sample: int) -> list[int]:
    """Evenly spaced indices so a draft samples across the whole output."""
    if total <= sample:
        return list(range(total))
    step = total / sample
    return sorted(int(i * step) for i in range(sample))


def draft_golden_set(
    record: dict[str, Any],
    items: list[tuple[str, dict[str, Any], str]],
    golden_dir: Path | None = None,
) -> Path:
    """Write one unscored golden skeleton for a stored run; human verifies."""
    scenario = str(record["scenario"])
    rubric_name = RUBRIC_BY_SCENARIO[scenario]
    _, rubric_version = load_rubric(rubric_name)
    golden_dir = golden_dir or GOLDEN_DIR
    golden_dir.mkdir(parents=True, exist_ok=True)
    path = golden_dir / f"{scenario}-{record['run_id']}.golden.json"
    if path.exists():
        raise DatasetError(
            f"{path} already exists — refusing to overwrite a possibly "
            "verified golden; delete it yourself if the draft is disposable."
        )
    payload = {
        "golden_version": GOLDEN_VERSION,
        "scenario": scenario,
        "rubric_name": rubric_name,
        "rubric_version": rubric_version,
        "run_id": str(record["run_id"]),
        "model_eval_id": str(record.get("model_eval_id") or ""),
        "verified_by": "",
        "verified_at": "",
        "items": [
            {
                "key": key,
                "payload": item_payload,
                "context": context,
                "human_scores": dict.fromkeys(RUBRIC_DIMENSIONS[scenario]),
                "human_flags": [],
                "note": "",
            }
            for key, item_payload, context in items
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), "utf-8")
    return path


def load_golden_sets(
    scenario: str, run_id: str, golden_dir: Path | None = None
) -> tuple[list[GoldenSet], int]:
    """(verified golden sets, pending draft count) for one scenario + run."""
    golden_dir = golden_dir or GOLDEN_DIR
    if not run_id or not golden_dir.is_dir():
        return [], 0
    verified: list[GoldenSet] = []
    pending = 0
    for path in sorted(golden_dir.glob(f"{scenario}-*.golden.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        if str(raw.get("run_id") or "") != run_id:
            continue
        golden_set = _parse_golden(path, raw, scenario)
        if golden_set.verified:
            verified.append(golden_set)
        else:
            pending += 1
    return verified, pending


def _parse_golden(path: Path, raw: dict, scenario: str) -> GoldenSet:
    if raw.get("golden_version") != GOLDEN_VERSION:
        raise DatasetError(f"{path}: golden_version must be {GOLDEN_VERSION}.")
    if raw.get("scenario") != scenario:
        raise DatasetError(f"{path}: scenario {raw.get('scenario')!r} mismatch.")
    dims = set(RUBRIC_DIMENSIONS[scenario])
    verified = bool(raw.get("verified_by")) and bool(raw.get("verified_at"))
    items_raw = raw.get("items")
    if not isinstance(items_raw, list) or not items_raw:
        raise DatasetError(f"{path}: items must be a non-empty list.")
    items = []
    for i, item in enumerate(items_raw):
        key = item.get("key")
        if not isinstance(key, str) or not key:
            raise DatasetError(f"{path} items[{i}]: missing 'key'.")
        if not isinstance(item.get("payload"), dict):
            raise DatasetError(f"{path} items[{i}]: 'payload' must be an object.")
        scores_raw = item.get("human_scores") or {}
        unknown = set(scores_raw) - dims
        if unknown:
            raise DatasetError(
                f"{path} items[{i}]: unknown dimensions {sorted(unknown)}; "
                f"the {scenario} rubric scores {sorted(dims)}."
            )
        scores: dict[str, float] = {}
        for dim, value in scores_raw.items():
            if value is None:
                if verified:
                    raise DatasetError(
                        f"{path} items[{i}]: {dim!r} is unscored but the set "
                        "is marked verified — score every dimension (-1 for "
                        "not-applicable) or clear verified_by/verified_at."
                    )
                continue
            if not isinstance(value, (int, float)):
                raise DatasetError(f"{path} items[{i}]: {dim!r} must be a number.")
            scores[dim] = float(value)
        items.append(
            GoldenItem(
                key=key,
                payload=item["payload"],
                context=str(item.get("context") or ""),
                human_scores=scores,
                human_flags=tuple(str(f) for f in item.get("human_flags") or []),
            )
        )
    return GoldenSet(
        path=path,
        scenario=scenario,
        rubric_name=str(raw.get("rubric_name") or scenario),
        rubric_version=str(raw.get("rubric_version") or ""),
        run_id=str(raw.get("run_id") or ""),
        verified_by=str(raw.get("verified_by") or ""),
        verified_at=str(raw.get("verified_at") or ""),
        items=tuple(items),
    )
