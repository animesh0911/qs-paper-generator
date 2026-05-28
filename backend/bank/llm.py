"""Provider-agnostic LLM client.

`LLMClient.complete(prompt, max_tokens) -> str` is the seam. Three adapters
ship out of the box: `AnthropicClient`, `OpenAIClient`, `GeminiClient`. Each
imports its SDK lazily — only the configured provider's SDK needs to be
installed at runtime.

`make_llm_client()` is the factory the rest of the codebase calls; it reads
`LLM_PROVIDER` (default `anthropic`) and the per-provider model env var.
"""
from __future__ import annotations

import os
from typing import Protocol


class LLMClient(Protocol):
    def complete(self, prompt: str, max_tokens: int = 2048) -> str: ...


class AnthropicClient:
    """Anthropic Claude. Reads ANTHROPIC_API_KEY (SDK convention)."""

    def __init__(self, model: str | None = None):
        self.model = model or os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")

    def complete(self, prompt: str, max_tokens: int = 2048) -> str:
        import anthropic

        client = anthropic.Anthropic()
        message = client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text


class OpenAIClient:
    """OpenAI GPT. Reads OPENAI_API_KEY (SDK convention)."""

    def __init__(self, model: str | None = None):
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

    def complete(self, prompt: str, max_tokens: int = 2048) -> str:
        from openai import OpenAI

        client = OpenAI()
        response = client.responses.create(
            model=self.model,
            input=prompt,
            max_output_tokens=max_tokens,
        )
        return response.output_text


class GeminiClient:
    """Google Gemini. Reads GEMINI_API_KEY (SDK convention)."""

    def __init__(self, model: str | None = None):
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    def complete(self, prompt: str, max_tokens: int = 2048) -> str:
        from google import genai

        client = genai.Client()
        response = client.models.generate_content(
            model=self.model,
            contents=prompt,
            config={"max_output_tokens": max_tokens},
        )
        return response.text


_CLIENTS: dict[str, type] = {
    "anthropic": AnthropicClient,
    "openai": OpenAIClient,
    "gemini": GeminiClient,
}


def make_llm_client() -> LLMClient:
    """Build the LLM client for the configured provider.

    Reads `LLM_PROVIDER` env var (default: `anthropic`).
    """
    provider = os.getenv("LLM_PROVIDER", "anthropic").lower()
    cls = _CLIENTS.get(provider)
    if cls is None:
        raise ValueError(
            f"Unknown LLM_PROVIDER {provider!r}. "
            f"Choose from: {sorted(_CLIENTS)}"
        )
    return cls()
