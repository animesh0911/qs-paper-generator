"""Shared scenario shapes and helpers."""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from evals.datasets import RESULTS_DIR
from evals.metering import Meter
from evals.records import RunRecord
from evals.registry import ModelSpec, cost_usd, to_inr

ARTIFACTS_DIR = RESULTS_DIR / "artifacts"


class EvalNotImplemented(RuntimeError):
    """A placeholder body was reached; the message names the owning issue."""


@dataclass(frozen=True)
class EvalUnit:
    """One cell of the run matrix: (scenario, arm, model, config, trial)."""

    scenario: str
    arm: str
    model_eval_id: str
    config: dict[str, Any]
    trial: int = 0

    @property
    def label(self) -> str:
        cfg = ",".join(f"{k}={v}" for k, v in sorted(self.config.items()))
        return f"{self.scenario}/{self.arm}/{self.model_eval_id}[{cfg}]#{self.trial}"


def new_record(unit: EvalUnit, spec: ModelSpec) -> RunRecord:
    return RunRecord(
        scenario=unit.scenario,
        arm=unit.arm,
        model_eval_id=spec.eval_id,
        provider=spec.provider,
        model=spec.model,
        config={**unit.config, "trial": unit.trial},
        pricing_verified=spec.pricing_verified,
    )


def settle_record(record: RunRecord, meter: Meter, spec: ModelSpec) -> RunRecord:
    """Copy metered totals + snapshot cost onto the record (report re-prices)."""
    record.calls = meter.calls
    record.input_tokens = meter.input_tokens
    record.output_tokens = meter.output_tokens
    record.cache_read_tokens = meter.cache_read_tokens
    record.ocr_pages = meter.ocr_pages
    record.cost_usd = cost_usd(
        spec,
        input_tokens=meter.input_tokens,
        output_tokens=meter.output_tokens,
        cache_read_tokens=meter.cache_read_tokens,
    )
    record.cost_inr = to_inr(record.cost_usd)
    return record


def save_artifact(record: RunRecord, payload: Any) -> None:
    """Persist raw model output so scoring never re-runs the paid phase."""
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    path = ARTIFACTS_DIR / f"{record.run_id}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    record.artifacts_path = str(path)


def load_artifact(record: dict) -> Any:
    path = Path(record.get("artifacts_path") or "")
    if not path.is_file():
        raise FileNotFoundError(
            f"Artifact for run {record.get('run_id')} not found at {path}; "
            "score must run on the machine/volume that ran the paid phase."
        )
    return json.loads(path.read_text(encoding="utf-8"))


@dataclass
class Stopwatch:
    """Wall-clock for the whole unit (includes non-LLM work, by design)."""

    started: float = field(default_factory=time.monotonic)

    @property
    def elapsed_ms(self) -> int:
        return int((time.monotonic() - self.started) * 1000)


@contextmanager
def unit_wall(record: RunRecord):
    watch = Stopwatch()
    try:
        yield
    finally:
        record.wall_ms = watch.elapsed_ms
