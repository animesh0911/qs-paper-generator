"""Budget gate: consent, unverified pricing, forecast cap, running tripwire."""

import pytest

from evals.budget import BudgetError, BudgetGate, UnitEstimate, estimate_units_usd
from evals.registry import get_model


def test_refuses_without_explicit_yes():
    gate = BudgetGate(cap_usd=5.0, yes=False)
    with pytest.raises(BudgetError, match="--yes"):
        gate.authorise({"google/gemini-3.5-flash": 0.10})


def test_refuses_unverified_pricing_by_default():
    gate = BudgetGate(cap_usd=5.0, yes=True)
    with pytest.raises(BudgetError, match="unverified"):
        gate.authorise({"qwen-3.7-max": None})
    BudgetGate(cap_usd=5.0, yes=True, allow_unverified_pricing=True).authorise(
        {"qwen-3.7-max": None}
    )


def test_refuses_forecast_over_cap():
    gate = BudgetGate(cap_usd=1.0, yes=True)
    with pytest.raises(BudgetError, match="exceeds cap"):
        gate.authorise({"google/gemini-3.5-flash": 1.5})


def test_running_spend_tripwire_stops_mid_matrix():
    gate = BudgetGate(cap_usd=0.10, yes=True)
    gate.authorise({"google/gemini-3.5-flash": 0.09})
    gate.charge(0.06)
    with pytest.raises(BudgetError, match="crossed the cap"):
        gate.charge(0.06)


def test_estimate_scales_with_units_and_none_propagates():
    spec = get_model("google/gemini-3.5-flash")
    units = [
        UnitEstimate(
            "u", calls=2, input_tokens_per_call=10_500, output_tokens_per_call=5_000
        )
    ]
    assert estimate_units_usd(spec, units) == pytest.approx(2 * 0.06075)
    assert estimate_units_usd(get_model("qwen-3.7-max"), units) is None
