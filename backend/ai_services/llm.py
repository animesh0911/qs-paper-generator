"""Shared LLM gateway — Gemini native-PDF extraction.

The bank ingestion path sends the source PDF straight to a multimodal model
(Gemini) and gets back structured questions via a provider-enforced response
schema. There is no text-extraction step (see ADR-0004). The rest of the backend
depends on ``LLMClient.extract`` rather than the Gemini SDK directly, so the
provider key stays server-side and the call shape is swappable.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from typing import Any, Protocol


class LLMClient(Protocol):
    def extract(self, pdf_bytes: bytes, prompt: str, response_schema: Any) -> dict: ...


# A generate function turns one PDF + prompt + schema into the model's raw JSON
# text. Injectable so tests exercise GeminiClient without importing google-genai
# or hitting the network.
GenerateFunc = Callable[..., str]

_DEFAULT_MODEL = "gemini-2.5-pro"


class GeminiClient:
    """Adapter around ``google-genai`` native-PDF structured output.

    Model from ``GEMINI_MODEL`` (default ``gemini-2.5-pro``), key from
    ``GEMINI_API_KEY``, request timeout from ``LLM_TIMEOUT_SECONDS``. ``extract``
    returns the parsed JSON dict the response schema guarantees.
    """

    def __init__(
        self,
        model: str | None = None,
        generate_func: GenerateFunc | None = None,
        timeout: float | None = None,
        api_key: str | None = None,
    ):
        self.model = model or os.getenv("GEMINI_MODEL", _DEFAULT_MODEL)
        self._generate_func = generate_func
        self.timeout = (
            timeout
            if timeout is not None
            else float(os.getenv("LLM_TIMEOUT_SECONDS", "60"))
        )
        self._api_key = api_key or os.getenv("GEMINI_API_KEY")

    def extract(self, pdf_bytes: bytes, prompt: str, response_schema: Any) -> dict:
        generate = self._generate_func or _load_default_generate(self._api_key)
        text = generate(
            model=self.model,
            pdf_bytes=pdf_bytes,
            prompt=prompt,
            response_schema=response_schema,
            timeout=self.timeout,
        )
        return json.loads(text)


def make_llm_client() -> LLMClient:
    return GeminiClient()


def _load_default_generate(api_key: str | None) -> GenerateFunc:
    """Build the real google-genai generate function (imported lazily)."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)

    def generate(
        *,
        model: str,
        pdf_bytes: bytes,
        prompt: str,
        response_schema: Any,
        timeout: float,
    ) -> str:
        response = client.models.generate_content(
            model=model,
            contents=[
                types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
                prompt,
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=response_schema,
                http_options=types.HttpOptions(timeout=int(timeout * 1000)),
            ),
        )
        return response.text

    return generate
