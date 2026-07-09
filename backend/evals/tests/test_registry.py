"""Registry invariants: the brief's matrix is complete and cost math is exact."""

from evals.registry import MODELS, cost_usd, get_model, to_inr

BRIEF_MODELS = (
    "google/gemini-3.5-flash",
    "deepseek-v4-flash",
    "deepseek-v4-pro",
    "google/gemini-3.1-flash-lite",
    "google/gemini-2.5-flash-lite",
    "gpt-oss-120b",
    "gpt-oss-20b",
    "qwen-3.7-plus",
    "qwen-3.7-max",
)


def test_every_brief_model_is_registered():
    for eval_id in BRIEF_MODELS:
        assert eval_id in MODELS


def test_only_report_backed_prices_are_verified():
    verified = {m.eval_id for m in MODELS.values() if m.pricing_verified}
    assert verified == {"google/gemini-3.5-flash", "deepseek-v4-flash"}


def test_cost_matches_cost_report_representative_call():
    # June 2026 cost report: 10.5k in / 5k out on Gemini 3.5 Flash = $0.060750.
    spec = get_model("google/gemini-3.5-flash")
    assert cost_usd(spec, input_tokens=10_500, output_tokens=5_000) == 0.06075


def test_cache_read_tokens_are_repriced_not_double_counted():
    spec = get_model("google/gemini-3.5-flash")
    cold = cost_usd(spec, input_tokens=10_000, output_tokens=0)
    warm = cost_usd(
        spec, input_tokens=10_000, output_tokens=0, cache_read_tokens=10_000
    )
    assert warm == 10_000 * 0.15 / 1_000_000
    assert warm < cold


def test_unverified_pricing_yields_none_not_zero():
    spec = get_model("qwen-3.7-max")
    assert cost_usd(spec, input_tokens=1000, output_tokens=1000) is None
    assert to_inr(None) is None


def test_env_overrides_route_through_the_production_seam_convention():
    spec = get_model("deepseek-v4-flash")
    assert spec.env_overrides("question_generation") == {
        "LLM_QUESTION_GENERATION_PROVIDER": "deepseek",
        "LLM_QUESTION_GENERATION_MODEL": "deepseek-v4-flash",
    }
