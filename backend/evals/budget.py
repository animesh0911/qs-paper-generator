"""Consent and budget guardrails for paid eval runs (Rule 13).

Contract every entrypoint obeys:

- **Dry-run is the default.** A bare invocation prints the unit matrix and the
  cost estimate, then exits without touching any network.
- **Paid runs need an explicit ``--yes``** — this is the CLI encoding of the
  project rule that a human consents before anything bills an LLM API.
- **A hard USD cap** (``--max-usd``, default :data:`DEFAULT_MAX_RUN_USD`, env
  ``EVALS_MAX_RUN_USD``) is checked twice: against the pre-run estimate, and
  against actual metered spend after every unit so a mis-estimate stops the
  matrix instead of finishing it.
- **Unverified pricing refuses to run** unless ``--allow-unverified-pricing``:
  tokens would still be recorded, but the runner cannot bound the bill.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from evals.registry import ModelSpec, cost_usd

DEFAULT_MAX_RUN_USD = 5.0


class BudgetError(RuntimeError):
    """Raised to stop a run before/once it would exceed its authorised spend."""


@dataclass(frozen=True)
class UnitEstimate:
    """A scenario's rough per-unit forecast (see each scenario's ESTIMATES)."""

    label: str
    calls: int
    input_tokens_per_call: int
    output_tokens_per_call: int
    ocr_pages: int = 0


def max_run_usd(cli_value: float | None = None) -> float:
    if cli_value is not None:
        return cli_value
    try:
        return float(os.getenv("EVALS_MAX_RUN_USD", DEFAULT_MAX_RUN_USD))
    except ValueError:
        return DEFAULT_MAX_RUN_USD


def estimate_units_usd(spec: ModelSpec, units: list[UnitEstimate]) -> float | None:
    """Forecast spend for ``units`` on ``spec``; None when pricing unverified."""
    total = 0.0
    for unit in units:
        per_call = cost_usd(
            spec,
            input_tokens=unit.input_tokens_per_call,
            output_tokens=unit.output_tokens_per_call,
        )
        if per_call is None:
            return None
        total += per_call * unit.calls
    return total


@dataclass
class BudgetGate:
    """Pre-run consent check + running spend tripwire for one invocation."""

    cap_usd: float
    yes: bool = False
    allow_unverified_pricing: bool = False
    spent_usd: float = field(default=0.0, init=False)

    def authorise(self, estimates: dict[str, float | None]) -> None:
        """Validate consent + forecast before the first paid call.

        ``estimates`` maps model eval_id → forecast USD (None = unpriceable).
        """
        if not self.yes:
            raise BudgetError(
                "Refusing paid run: pass --yes to consent to LLM API spend "
                "(dry-run is the default)."
            )
        unpriced = sorted(k for k, v in estimates.items() if v is None)
        if unpriced and not self.allow_unverified_pricing:
            raise BudgetError(
                "Refusing paid run: pricing unverified for "
                f"{', '.join(unpriced)}. Fill evals/registry.py rates or pass "
                "--allow-unverified-pricing (spend will be unbounded by price)."
            )
        forecast = sum(v for v in estimates.values() if v is not None)
        if forecast > self.cap_usd:
            raise BudgetError(
                f"Refusing paid run: forecast ${forecast:.2f} exceeds cap "
                f"${self.cap_usd:.2f}. Shrink the matrix or raise --max-usd."
            )

    def charge(self, unit_cost_usd: float | None) -> None:
        """Record actual spend after a unit; trip once the cap is crossed."""
        if unit_cost_usd:
            self.spent_usd += unit_cost_usd
        if self.spent_usd > self.cap_usd:
            raise BudgetError(
                f"Stopping run: metered spend ${self.spent_usd:.2f} crossed the "
                f"cap ${self.cap_usd:.2f}. Completed units are recorded; "
                "resume with a narrower matrix or a higher --max-usd."
            )
