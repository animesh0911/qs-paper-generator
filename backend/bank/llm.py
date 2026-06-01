"""Compatibility exports for bank ingestion LLM calls.

The shared implementation lives in ``ai_services.llm`` so editor AI, ingestion
tagging, and future paper review use one provider gateway instead of separate
SDK wrappers.
"""

from ai_services.llm import (
    LiteLLMClient,
    LLMClient,
    make_llm_client,
    provider_model,
)

# Re-exported for callers that still import the gateway from ``bank.llm``
# (e.g. ``bank.ingestor``). Listed here so the unused-import lint keeps them.
__all__ = [
    "LLMClient",
    "LiteLLMClient",
    "make_llm_client",
    "provider_model",
    "AnthropicClient",
    "OpenAIClient",
    "GeminiClient",
]


class AnthropicClient(LiteLLMClient):
    """Backward-compatible name. Configure via ``LLM_MODEL`` or Anthropic env."""

    def __init__(self, model: str | None = None):
        super().__init__(model=provider_model("anthropic", model))


class OpenAIClient(LiteLLMClient):
    """Backward-compatible name. Configure via ``LLM_MODEL`` or OpenAI env."""

    def __init__(self, model: str | None = None):
        super().__init__(model=provider_model("openai", model))


class GeminiClient(LiteLLMClient):
    """Backward-compatible name. Configure via ``LLM_MODEL`` or Gemini env."""

    def __init__(self, model: str | None = None):
        super().__init__(model=provider_model("gemini", model))
