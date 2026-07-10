"""Cost accounting for live upload extraction evals.

Costing is deliberately separate from model execution. The upload eval runner
records token/page usage; this module turns that usage into dollars using the
best available price adapter.
"""

from __future__ import annotations

import json
import urllib.request
from functools import cache

from evals.registry import MODELS, cost_usd

DEFAULT_MISTRAL_OCR_USD_PER_1000_PAGES = 1.0


def price_ocr_pages(
    pages: int,
    *,
    usd_per_1000_pages: float | None = DEFAULT_MISTRAL_OCR_USD_PER_1000_PAGES,
) -> float | None:
    """Price OCR by source PDF page count."""
    if usd_per_1000_pages is None:
        return None
    return pages * usd_per_1000_pages / 1000


def price_llm_tokens(
    *,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
) -> float | None:
    """Best-effort price for arbitrary live eval structuring models."""
    if provider == "openrouter":
        pricing = _openrouter_pricing().get(model)
        if pricing:
            return (
                input_tokens * pricing["prompt"]
                + output_tokens * pricing["completion"]
            )

    spec = MODELS.get(model)
    if spec:
        return cost_usd(
            spec,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read_tokens,
        )
    return None


def total_cost(*costs: float | None) -> float | None:
    """Return total only when every cost input is priced."""
    if any(cost is None for cost in costs):
        return None
    return sum(cost for cost in costs if cost is not None)


@cache
def _openrouter_pricing() -> dict[str, dict[str, float]]:
    try:
        with urllib.request.urlopen(
            "https://openrouter.ai/api/v1/models", timeout=10
        ) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception:  # noqa: BLE001 - pricing failure should not fail the run
        return {}
    prices = {}
    for model in payload.get("data") or []:
        pricing = model.get("pricing") or {}
        try:
            prices[str(model["id"])] = {
                "prompt": float(pricing["prompt"]),
                "completion": float(pricing["completion"]),
            }
        except (KeyError, TypeError, ValueError):
            continue
    return prices
