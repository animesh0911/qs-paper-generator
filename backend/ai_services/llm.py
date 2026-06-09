"""Shared LLM access — the model seam plus the bespoke Gemini extraction path.

Two patterns live here, by design (ADR-0005):

- **model seam** (``make_chat_model``) — the "altitude 1" pattern and the single
  place a provider-agnostic LangChain chat model is built. It owns
  provider/model/key/retry and attaches token/latency telemetry, so any
  text-generation surface (answer generation today; verification/editor later)
  swaps Gemini↔Claude↔OpenAI↔local by config without touching call sites.

- **native-PDF extraction** (``LLMClient`` / ``GeminiClient``) — the bespoke
  ``google-genai`` ingestion path: sends the source PDF straight to a multimodal
  model and gets back structured questions via a provider-enforced response
  schema (ADR-0004). Extraction now also rides the seam (``SeamExtractor`` in
  ``bank.ingestor``, via ``with_structured_output`` — #156); this bespoke client
  is kept revertable until the benchmark parity run is accepted (ADR-0005).
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol
from uuid import UUID

from langchain.chat_models import init_chat_model
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.language_models import BaseChatModel
from langchain_core.outputs import LLMResult

logger = logging.getLogger(__name__)


class LLMClient(Protocol):
    def extract(self, pdf_bytes: bytes, prompt: str, response_schema: Any) -> dict: ...


# A generate function turns one PDF + prompt + schema into the model's raw JSON
# text. Injectable so tests exercise GeminiClient without importing google-genai
# or hitting the network.
GenerateFunc = Callable[..., str]

_DEFAULT_MODEL = "gemini-3.5-flash"
# Gemini thinking budget (tokens). -1 = dynamic (model decides — the default),
# 0 = thinking off, >0 = a fixed cap. Thinking lets the model reason before
# emitting the schema-constrained JSON, which helps recall/structuring on dense
# scanned pages without polluting the structured output. Override per env.
_DEFAULT_THINKING_BUDGET = -1


def _thinking_budget() -> int:
    try:
        return int(os.getenv("GEMINI_THINKING_BUDGET", _DEFAULT_THINKING_BUDGET))
    except ValueError:
        return _DEFAULT_THINKING_BUDGET


class GeminiClient:
    """Adapter around ``google-genai`` native-PDF structured output.

    Model from ``GEMINI_MODEL`` (default ``gemini-3.5-flash``), key from
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
        # Generous default: a pro-tier model on a full scanned bilingual paper
        # can take minutes, and ingestion is an offline batch (latency
        # irrelevant — ADR-0004). 60s reliably 504s on scanned PDFs.
        self.timeout = (
            timeout
            if timeout is not None
            else float(os.getenv("LLM_TIMEOUT_SECONDS", "240"))
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
                thinking_config=types.ThinkingConfig(
                    thinking_budget=_thinking_budget()
                ),
                http_options=types.HttpOptions(timeout=int(timeout * 1000)),
            ),
        )
        return response.text

    return generate


# ---------------------------------------------------------------------------
# Model seam (ADR-0005) — the one place a provider-agnostic LangChain chat model
# is built. Provider/model/key/retry resolve from config here so call sites stay
# provider-blind, and an observability callback rides every call.
# ---------------------------------------------------------------------------


class ModelPurpose(StrEnum):
    """The logical role a chat model is built for.

    A purpose lets one surface (answer generation, extraction today;
    verification and the editor later) resolve to its own provider/model via env,
    falling back to the global default — without other surfaces noticing.
    """

    ANSWER_GENERATION = "answer_generation"
    # Bank ingestion. Moved onto the seam (#156) via LangChain
    # ``with_structured_output``; gated behind a benchmark-proven parity run
    # (ADR-0005). Resolves to the Gemini extraction model by default.
    EXTRACTION = "extraction"


@dataclass(frozen=True)
class _Provider:
    """How a short provider name maps onto LangChain + our env convention."""

    init_id: str  # init_chat_model's model_provider id
    env_prefix: str  # <PREFIX>_MODEL / <PREFIX>_API_KEY (matches docker-compose)
    api_key_kwarg: str | None  # constructor kwarg the integration reads, if any
    default_model: str | None


# Short names are what LLM_PROVIDER carries (docker-compose passes GEMINI_*/
# ANTHROPIC_*/OPENAI_* by this convention). Gemini is the default so answer
# generation rides the same model as extraction; ``ollama`` is the local-capable
# provider proving the seam swaps without a hosted key.
_PROVIDERS: dict[str, _Provider] = {
    "gemini": _Provider("google_genai", "GEMINI", "google_api_key", _DEFAULT_MODEL),
    "anthropic": _Provider("anthropic", "ANTHROPIC", "api_key", None),
    "openai": _Provider("openai", "OPENAI", "api_key", None),
    "ollama": _Provider("ollama", "OLLAMA", None, None),
}

_DEFAULT_PROVIDER = "gemini"
_DEFAULT_MAX_RETRIES = 2

# init_chat_model factory signature — injectable so tests build a model without a
# provider integration package or an API key (Rules 9/11; no module patching).
InitChatModel = Callable[..., BaseChatModel]


@dataclass(frozen=True)
class ChatModelConfig:
    """The resolved recipe handed to ``init_chat_model`` — pure data, no I/O, so
    config resolution is testable without constructing a real model."""

    provider: str  # init_chat_model model_provider id (e.g. "google_genai")
    model: str
    init_kwargs: dict[str, Any]


def _max_retries() -> int:
    try:
        return int(os.getenv("LLM_MAX_RETRIES", _DEFAULT_MAX_RETRIES))
    except ValueError:
        return _DEFAULT_MAX_RETRIES


def _purpose_env(purpose: ModelPurpose, suffix: str) -> str | None:
    """Per-purpose override, e.g. ``LLM_ANSWER_GENERATION_MODEL``."""
    return os.getenv(f"LLM_{purpose.value.upper()}_{suffix}")


def resolve_chat_model_config(purpose: ModelPurpose) -> ChatModelConfig:
    """Resolve provider/model/key/retry for ``purpose`` from env.

    Precedence: a purpose-specific override (``LLM_<PURPOSE>_PROVIDER`` /
    ``_MODEL``) beats the global default (``LLM_PROVIDER`` / ``<PREFIX>_MODEL``),
    which beats the built-in default (gemini / its extraction model). Fails loud
    (Rule 12) on an unknown provider or a provider with no model configured,
    rather than constructing something the caller didn't ask for.
    """
    name = (
        _purpose_env(purpose, "PROVIDER")
        or os.getenv("LLM_PROVIDER")
        or _DEFAULT_PROVIDER
    ).lower()
    provider = _PROVIDERS.get(name)
    if provider is None:
        raise ValueError(f"Unknown LLM provider {name!r}; known: {sorted(_PROVIDERS)}.")
    model = (
        _purpose_env(purpose, "MODEL")
        or os.getenv(f"{provider.env_prefix}_MODEL")
        or provider.default_model
    )
    if not model:
        raise ValueError(
            f"No model configured for provider {name!r}; set "
            f"{provider.env_prefix}_MODEL or LLM_{purpose.value.upper()}_MODEL."
        )
    init_kwargs: dict[str, Any] = {"max_retries": _max_retries()}
    if provider.api_key_kwarg:
        key = os.getenv(f"{provider.env_prefix}_API_KEY")
        if key:
            init_kwargs[provider.api_key_kwarg] = key
    return ChatModelConfig(
        provider=provider.init_id, model=model, init_kwargs=init_kwargs
    )


class LlmCallObserver(BaseCallbackHandler):
    """Captures token/latency telemetry at the seam — the one point every model
    call passes through (ADR-0005: observability belongs here, not in per-call
    graph wrappers). Logs at INFO and never raises: telemetry must not be able to
    break a generation run.
    """

    def __init__(self, purpose: ModelPurpose):
        self._purpose = purpose.value
        self._started: dict[UUID, float] = {}

    # Chat models fire on_chat_model_start; the (legacy) text path fires
    # on_llm_start. Both terminate in on_llm_end, so we mark either start.
    def on_chat_model_start(self, serialized, messages, *, run_id, **kwargs):
        self._started[run_id] = time.monotonic()

    def on_llm_start(self, serialized, prompts, *, run_id, **kwargs):
        self._started[run_id] = time.monotonic()

    def on_llm_end(self, response: LLMResult, *, run_id, **kwargs):
        logger.info(
            "llm_call purpose=%s latency_ms=%d tokens=%s",
            self._purpose,
            self._elapsed_ms(run_id),
            self._token_usage(response),
        )

    def on_llm_error(self, error: BaseException, *, run_id, **kwargs):
        logger.warning(
            "llm_call_error purpose=%s latency_ms=%d error=%s",
            self._purpose,
            self._elapsed_ms(run_id),
            error,
        )

    def _elapsed_ms(self, run_id: UUID) -> int:
        start = self._started.pop(run_id, None)
        return 0 if start is None else int((time.monotonic() - start) * 1000)

    @staticmethod
    def _token_usage(response: LLMResult) -> dict:
        # Providers surface counts in one of two places; a fake model has
        # neither, so an empty dict is the honest answer rather than a crash.
        out = response.llm_output or {}
        usage = out.get("token_usage") or out.get("usage")
        if usage:
            return dict(usage)
        try:
            meta = response.generations[0][0].message.usage_metadata  # type: ignore[attr-defined]
        except (AttributeError, IndexError):
            meta = None
        return dict(meta) if meta else {}


def make_chat_model(
    purpose: ModelPurpose,
    *,
    init: InitChatModel | None = None,
) -> BaseChatModel:
    """Build the configured chat model for ``purpose`` (the model seam).

    Resolves the recipe via :func:`resolve_chat_model_config`, then constructs
    the model through LangChain's ``init_chat_model`` with an
    :class:`LlmCallObserver` attached so every call is observable. ``init`` is
    injectable so tests build a model without a provider integration installed.
    """
    cfg = resolve_chat_model_config(purpose)
    init = init or init_chat_model
    return init(
        cfg.model,
        model_provider=cfg.provider,
        callbacks=[LlmCallObserver(purpose)],
        **cfg.init_kwargs,
    )
