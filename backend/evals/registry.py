"""Model matrix and pricing registry for eval runs.

One :class:`ModelSpec` per candidate model. The spec carries two separable
concerns:

- **routing** — which seam provider serves it and what model id that provider's
  API expects. Applied via the same env vars production resolves
  (``LLM_<PURPOSE>_PROVIDER`` / ``LLM_<PURPOSE>_MODEL`` — see
  ``ai_services.llm.resolve_chat_model_config``), so eval runs exercise the
  exact production code path for that configuration.
- **pricing** — USD per 1M tokens, entered by hand from provider price pages
  and stamped with ``PRICING_AS_OF``. Entries whose price is unconfirmed carry
  ``pricing_verified=False`` and ``None`` rates; the budget gate refuses paid
  runs for them unless explicitly overridden, and cost is recomputed at report
  time from recorded token counts, so verifying a price later re-prices past
  runs without re-running them.

Never guess a price into a ``verified`` slot: a wrong price silently corrupts
every per-run and per-user/month number downstream.
"""

from __future__ import annotations

from dataclasses import dataclass

# Stamp of when the verified prices below were last checked against provider
# price pages. Bump whenever any rate is edited.
PRICING_AS_OF = "2026-07-13"  # OpenRouter listing + Mistral OCR pricing page

# FX planning rate from docs/pricing_model.md ("FX assumption: ₹88 / USD").
INR_PER_USD = 88.0


@dataclass(frozen=True)
class ModelSpec:
    """Routing + pricing for one eval candidate model."""

    eval_id: str  # the id used in eval CLIs/reports (matches the eval brief)
    provider: str  # seam provider name (ai_services.llm._PROVIDERS key)
    model: str  # model id the provider's API expects
    usd_per_1m_input: float | None
    usd_per_1m_output: float | None
    usd_per_1m_cache_read: float | None = None
    pricing_verified: bool = False
    notes: str = ""

    def env_overrides(self, purpose_value: str) -> dict[str, str]:
        """Env vars that route ``purpose`` to this model through the real seam."""
        prefix = f"LLM_{purpose_value.upper()}"
        return {f"{prefix}_PROVIDER": self.provider, f"{prefix}_MODEL": self.model}


@dataclass(frozen=True)
class OcrEngineSpec:
    """Pricing/identity for a page-image OCR engine (extraction scenario)."""

    eval_id: str
    usd_per_page: float | None
    pricing_verified: bool = False
    notes: str = ""


# ---------------------------------------------------------------------------
# The candidate matrix (from the eval brief). All chat candidates route via
# OpenRouter (the deploy convention — one OPENROUTER_API_KEY, no per-provider
# keys); model ids and rates were read from the live openrouter.ai/api/v1/models
# listing on PRICING_AS_OF. The one exception (gemini-2.5-flash-lite) is not
# listed on OpenRouter and stays unverified until priced natively or dropped.
# ---------------------------------------------------------------------------

_OPENROUTER_LISTING = "openrouter.ai/api/v1/models listing, checked 2026-07-10"

MODELS: dict[str, ModelSpec] = {
    spec.eval_id: spec
    for spec in (
        ModelSpec(
            eval_id="google/gemini-3.5-flash",
            provider="openrouter",
            model="google/gemini-3.5-flash",
            usd_per_1m_input=1.50,
            usd_per_1m_output=9.00,
            usd_per_1m_cache_read=0.15,
            pricing_verified=True,
            notes=(
                "Production default (ADR-0004/0005). Rates: "
                f"{_OPENROUTER_LISTING}; identical to the native-API rates in "
                "the June 2026 cost report."
            ),
        ),
        ModelSpec(
            eval_id="deepseek-v4-flash",
            provider="openrouter",
            model="deepseek/deepseek-v4-flash",
            usd_per_1m_input=0.09,
            usd_per_1m_output=0.18,
            usd_per_1m_cache_read=0.018,
            pricing_verified=True,
            notes=(
                f"Rates: {_OPENROUTER_LISTING}. Cheaper than DeepSeek's "
                "native API (June 2026 report: 0.14/0.28) — reprice if "
                "routing ever moves off OpenRouter."
            ),
        ),
        ModelSpec(
            eval_id="deepseek-v4-pro",
            provider="openrouter",
            model="deepseek/deepseek-v4-pro",
            usd_per_1m_input=0.435,
            usd_per_1m_output=0.87,
            usd_per_1m_cache_read=0.003625,
            pricing_verified=True,
            notes=f"Rates: {_OPENROUTER_LISTING}.",
        ),
        ModelSpec(
            eval_id="google/gemini-3.1-flash-lite",
            provider="openrouter",
            model="google/gemini-3.1-flash-lite",
            usd_per_1m_input=0.25,
            usd_per_1m_output=1.50,
            usd_per_1m_cache_read=0.025,
            pricing_verified=True,
            notes=f"Rates: {_OPENROUTER_LISTING}.",
        ),
        ModelSpec(
            eval_id="google/gemini-2.5-flash-lite",
            provider="gemini",
            model="gemini-2.5-flash-lite",
            usd_per_1m_input=None,
            usd_per_1m_output=None,
            notes=(
                "Not listed on OpenRouter (checked 2026-07-10), so this stays "
                "on the native gemini provider (needs GEMINI_API_KEY) with "
                "rates unverified — price from the Google AI Studio page or "
                "drop it from the matrix."
            ),
        ),
        ModelSpec(
            eval_id="gpt-oss-120b",
            provider="openrouter",
            model="openai/gpt-oss-120b",
            usd_per_1m_input=0.036,
            usd_per_1m_output=0.18,
            pricing_verified=True,
            notes=(
                f"Rates: {_OPENROUTER_LISTING} (default routing; open-weights "
                "prices vary by host, so re-check before large runs)."
            ),
        ),
        ModelSpec(
            eval_id="gpt-oss-20b",
            provider="openrouter",
            model="openai/gpt-oss-20b",
            usd_per_1m_input=0.029,
            usd_per_1m_output=0.14,
            pricing_verified=True,
            notes=(
                f"Rates: {_OPENROUTER_LISTING} (default routing; open-weights "
                "prices vary by host, so re-check before large runs)."
            ),
        ),
        ModelSpec(
            eval_id="qwen-3.7-plus",
            provider="openrouter",
            model="qwen/qwen3.7-plus",
            usd_per_1m_input=0.32,
            usd_per_1m_output=1.28,
            usd_per_1m_cache_read=0.064,
            pricing_verified=True,
            notes=(
                f"Rates: {_OPENROUTER_LISTING}. NB the listed id is "
                "qwen/qwen3.7-plus — the previously guessed qwen/qwen-3.7-plus "
                "does not exist."
            ),
        ),
        ModelSpec(
            eval_id="qwen-3.7-max",
            provider="openrouter",
            model="qwen/qwen3.7-max",
            usd_per_1m_input=1.25,
            usd_per_1m_output=3.75,
            usd_per_1m_cache_read=0.25,
            pricing_verified=True,
            notes=f"Rates: {_OPENROUTER_LISTING}. Listed id is qwen/qwen3.7-max.",
        ),
    )
}

OCR_ENGINES: dict[str, OcrEngineSpec] = {
    spec.eval_id: spec
    for spec in (
        OcrEngineSpec(
            eval_id="mistral-ocr",
            usd_per_page=0.004,
            pricing_verified=True,
            notes=(
                "Production OCR arm (bank.ocr_extractor). "
                "Mistral OCR 4 rate: $4 per 1,000 pages, verified 2026-07-13 "
                "from https://mistral.ai/pricing/api/."
            ),
        ),
        OcrEngineSpec(
            eval_id="docling",
            usd_per_page=0.0,
            pricing_verified=True,
            notes=(
                "Local/free (already a corpus-side dependency). Deterministic "
                "guardrail arm: page count + text-layer stats before paid OCR."
            ),
        ),
    )
}


def get_model(eval_id: str) -> ModelSpec:
    try:
        return MODELS[eval_id]
    except KeyError:
        known = ", ".join(sorted(MODELS))
        raise KeyError(f"Unknown eval model {eval_id!r}. Known: {known}") from None


def cost_usd(
    spec: ModelSpec,
    *,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
) -> float | None:
    """Price one call's token usage; ``None`` when pricing is unverified.

    ``input_tokens`` follows the LangChain ``usage_metadata`` convention of
    counting *all* prompt tokens including cached ones, so cached tokens are
    re-priced at the cache-read rate and subtracted from the fresh-input bucket.
    """
    if spec.usd_per_1m_input is None or spec.usd_per_1m_output is None:
        return None
    cache_rate = (
        spec.usd_per_1m_cache_read
        if spec.usd_per_1m_cache_read is not None
        else spec.usd_per_1m_input
    )
    fresh_input = max(input_tokens - cache_read_tokens, 0)
    return (
        fresh_input * spec.usd_per_1m_input
        + cache_read_tokens * cache_rate
        + output_tokens * spec.usd_per_1m_output
    ) / 1_000_000


def to_inr(usd: float | None) -> float | None:
    return None if usd is None else usd * INR_PER_USD
