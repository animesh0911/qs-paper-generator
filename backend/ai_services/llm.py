"""Shared LLM gateway built on LiteLLM.

The rest of the backend should depend on ``LLMClient.complete`` instead of
provider SDKs. LiteLLM gives us one call shape for OpenAI, Anthropic, Gemini,
and future providers while keeping provider keys server-side.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any, Protocol


class LLMClient(Protocol):
    def complete(self, prompt: str, max_tokens: int = 2048) -> str: ...


CompletionFunc = Callable[..., Any]


_DEFAULT_PROVIDER_MODELS = {
    "anthropic": ("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001"),
    "openai": ("OPENAI_MODEL", "gpt-4.1-mini"),
    "gemini": ("GEMINI_MODEL", "gemini-2.5-flash"),
}


def configured_model() -> str:
    """Return the LiteLLM model id from env.

    Prefer ``LLM_MODEL`` because LiteLLM expects provider-prefixed model ids
    such as ``anthropic/claude-...`` or ``openai/gpt-...``. The older
    ``LLM_PROVIDER`` + provider-specific model env vars remain supported so
    the existing ingestion path keeps working after the lift-and-shift.
    """
    model = os.getenv("LLM_MODEL")
    if model:
        return model

    provider = os.getenv("LLM_PROVIDER", "anthropic").lower()
    return provider_model(provider)


def provider_model(provider: str, model: str | None = None) -> str:
    """Return a provider-prefixed LiteLLM model id."""
    provider = provider.lower()
    model_env, fallback_model = _DEFAULT_PROVIDER_MODELS.get(
        provider,
        _DEFAULT_PROVIDER_MODELS["anthropic"],
    )
    selected_model = model or os.getenv(model_env, fallback_model)
    if "/" in selected_model:
        return selected_model
    return f"{provider}/{selected_model}"


class LiteLLMClient:
    """Small adapter around ``litellm.completion``.

    ``completion_func`` is injectable so tests can verify our normalization
    without importing or calling the real LiteLLM package.
    """

    def __init__(
        self,
        model: str | None = None,
        completion_func: CompletionFunc | None = None,
        timeout: float | None = None,
    ):
        self.model = model or configured_model()
        self._completion_func = completion_func
        self.timeout = timeout or float(os.getenv("LLM_TIMEOUT_SECONDS", "30"))

    def complete(self, prompt: str, max_tokens: int = 2048) -> str:
        completion = self._completion_func or _load_litellm_completion()
        response = completion(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            timeout=self.timeout,
        )
        return _extract_text(response)


def make_llm_client() -> LLMClient:
    return LiteLLMClient()


def _load_litellm_completion() -> CompletionFunc:
    from litellm import completion

    return completion


def _extract_text(response: Any) -> str:
    """Normalize LiteLLM's OpenAI-compatible response into plain text."""
    choices = _get(response, "choices")
    if not choices:
        raise ValueError("LLM response did not include choices.")

    first = choices[0]
    message = _get(first, "message")
    content = _get(message, "content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            else:
                text = _get(item, "text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)
    raise ValueError("LLM response message did not include text content.")


def _get(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)
