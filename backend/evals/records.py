"""Run records: the durable, versioned result rows every phase reads/writes.

One :class:`RunRecord` per (scenario, arm, model, config, trial). Records are
append-only JSONL under ``/content/eval/results/`` so paid runs, scoring, and
reporting are decoupled: scoring mutates a *copy* of the record (adds
``accuracy``), reporting never mutates anything.

Reproducibility fields (``fingerprint``) pin what produced a number: git SHA,
prompt fingerprints, pricing stamp, and the exact resolved provider/model.
When any of those change, rows are not comparable and the report says so
rather than averaging across them.
"""

from __future__ import annotations

import json
import subprocess
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from evals.registry import PRICING_AS_OF

SCHEMA_VERSION = 1


def _git_sha() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        sha = out.stdout.strip()
        return sha or "unknown"
    except OSError:
        return "unknown"


def fingerprint(extra: dict[str, str] | None = None) -> dict[str, str]:
    """Environment fingerprint stamped onto every record."""
    fp = {"git_sha": _git_sha(), "pricing_as_of": PRICING_AS_OF}
    fp.update(extra or {})
    return fp


@dataclass
class CallMetrics:
    """One model/OCR call inside a run, as recorded by ``evals.metering``."""

    kind: str  # "chat" | "ocr"
    model: str
    latency_ms: int
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    pages: int = 0  # OCR calls meter pages, not tokens
    error: str = ""


@dataclass
class RunRecord:
    """One eval unit's outcome — everything the report needs, self-contained."""

    scenario: str  # "generation" | "extraction" | "answers"
    arm: str  # scenario-specific variant, e.g. "native_pdf" | "ocr_mistral"
    model_eval_id: str
    provider: str
    model: str
    config: dict[str, Any]  # batch_size / pages / chunk_size / dataset / trial
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    schema_version: int = SCHEMA_VERSION
    started_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds")
    )
    fingerprint: dict[str, str] = field(default_factory=fingerprint)
    wall_ms: int = 0  # whole-unit wall clock (includes non-LLM work)
    calls: list[CallMetrics] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    ocr_pages: int = 0
    cost_usd: float | None = None  # snapshot; report re-prices from tokens
    cost_inr: float | None = None
    pricing_verified: bool = False
    batch_size: int = 0  # the brief's unit: requested questions / pages / etc.
    delivered: int = 0  # what actually came back (questions, answers, ...)
    accuracy: dict[str, Any] | None = None  # filled by the score phase
    artifacts_path: str = ""  # raw model output JSON for re-scoring
    success: bool = False
    error: str = ""

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, sort_keys=True)


def append_records(path: Path, records: list[RunRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for record in records:
            fh.write(record.to_json() + "\n")


def read_records(path: Path) -> list[dict[str, Any]]:
    """Read raw record dicts (schema-checked, not dataclass-coerced)."""
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        version = row.get("schema_version")
        if version != SCHEMA_VERSION:
            raise ValueError(
                f"{path}:{line_no} has schema_version={version!r}; "
                f"this code reads {SCHEMA_VERSION}. Migrate or re-run."
            )
        rows.append(row)
    return rows
