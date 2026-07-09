"""Small, dependency-free aggregation helpers for eval reports.

Evals run few trials (default 3) of expensive units, so we report honest
small-sample numbers: mean ± sample std and min/max for per-run metrics,
p50/p95 for per-call latencies pooled across a group's runs. No significance
theatre at n=3 — the report shows spread and lets the reader judge.
"""

from __future__ import annotations

import math
from collections.abc import Sequence


def mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def sample_std(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = mean(values)
    return math.sqrt(sum((v - m) ** 2 for v in values) / (len(values) - 1))


def percentile(values: Sequence[float], pct: float) -> float:
    """Nearest-rank percentile; robust for the small n evals produce."""
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, math.ceil(pct / 100 * len(ordered)))
    return ordered[rank - 1]


def summarise(values: Sequence[float]) -> dict[str, float]:
    return {
        "n": len(values),
        "mean": mean(values),
        "std": sample_std(values),
        "min": min(values) if values else 0.0,
        "max": max(values) if values else 0.0,
        "p50": percentile(values, 50),
        "p95": percentile(values, 95),
    }
