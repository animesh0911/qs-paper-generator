"""Per-call token/latency metering that rides the production model seam.

Production already exposes the two injection points this module needs
(Rules 9/11, ADR-0005), so nothing in ``bank``/``workflows`` changes:

- ``make_chat_model(purpose, init=...)`` — we wrap ``init_chat_model`` to
  append a recording callback *after* production's own ``LlmCallObserver``.
  Config resolution (provider/model/key/retry from env) stays 100% production.
- every workflow class takes a model factory (``make_model=`` /
  ``chat_model=`` / ``generator_factory=``) — we hand it the metered factory.

Model routing is applied with :func:`seam_env`, which sets the same
``LLM_<PURPOSE>_PROVIDER`` / ``_MODEL`` env vars a deploy would set, so the
run measures the config it claims to measure.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.language_models import BaseChatModel
from langchain_core.outputs import LLMResult

from evals.records import CallMetrics


def _usage_from_result(response: LLMResult) -> tuple[int, int, int]:
    """Normalise (input, output, cache_read) tokens from an LLMResult.

    Mirrors the two places ``ai_services.llm.LlmCallObserver`` reads, then
    normalises provider naming (prompt/completion vs input/output).
    """
    usage: dict[str, Any] = {}
    out = response.llm_output or {}
    usage = dict(out.get("token_usage") or out.get("usage") or {})
    if not usage:
        try:
            meta = response.generations[0][0].message.usage_metadata  # type: ignore[attr-defined]
        except (AttributeError, IndexError):
            meta = None
        usage = dict(meta) if meta else {}
    input_tokens = int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
    output_tokens = int(
        usage.get("output_tokens") or usage.get("completion_tokens") or 0
    )
    details = usage.get("input_token_details") or {}
    cache_read = int(details.get("cache_read") or usage.get("cache_read") or 0)
    return input_tokens, output_tokens, cache_read


class Meter:
    """Accumulates :class:`CallMetrics` for one eval unit (one RunRecord)."""

    def __init__(self, model_label: str):
        self.model_label = model_label
        self.calls: list[CallMetrics] = []

    # -- totals the RunRecord copies over -------------------------------
    @property
    def input_tokens(self) -> int:
        return sum(c.input_tokens for c in self.calls)

    @property
    def output_tokens(self) -> int:
        return sum(c.output_tokens for c in self.calls)

    @property
    def cache_read_tokens(self) -> int:
        return sum(c.cache_read_tokens for c in self.calls)

    @property
    def ocr_pages(self) -> int:
        return sum(c.pages for c in self.calls)

    def record_ocr(self, *, pages: int, latency_ms: int, model: str = "ocr") -> None:
        """OCR calls are metered by page, not token (extraction scenario)."""
        self.calls.append(
            CallMetrics(kind="ocr", model=model, latency_ms=latency_ms, pages=pages)
        )


class MeteringCallback(BaseCallbackHandler):
    """Records one CallMetrics per chat-model call into a :class:`Meter`."""

    def __init__(self, meter: Meter):
        self._meter = meter
        self._started: dict[UUID, float] = {}

    def on_chat_model_start(self, serialized, messages, *, run_id, **kwargs):
        self._started[run_id] = time.monotonic()

    def on_llm_start(self, serialized, prompts, *, run_id, **kwargs):
        self._started[run_id] = time.monotonic()

    def on_llm_end(self, response: LLMResult, *, run_id, **kwargs):
        input_tokens, output_tokens, cache_read = _usage_from_result(response)
        self._meter.calls.append(
            CallMetrics(
                kind="chat",
                model=self._meter.model_label,
                latency_ms=self._elapsed_ms(run_id),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cache_read_tokens=cache_read,
            )
        )

    def on_llm_error(self, error: BaseException, *, run_id, **kwargs):
        self._meter.calls.append(
            CallMetrics(
                kind="chat",
                model=self._meter.model_label,
                latency_ms=self._elapsed_ms(run_id),
                error=str(error),
            )
        )

    def _elapsed_ms(self, run_id: UUID) -> int:
        start = self._started.pop(run_id, None)
        return 0 if start is None else int((time.monotonic() - start) * 1000)


def metered_make_model(
    meter: Meter,
    *,
    base_init: Callable[..., BaseChatModel] | None = None,
) -> Callable[..., BaseChatModel]:
    """A drop-in ``make_chat_model`` that also meters every call.

    Delegates to the real ``ai_services.llm.make_chat_model`` (env resolution,
    retries, production observer) and only appends the recording callback via
    the ``init`` seam. ``base_init`` is injectable so tests meter a fake model
    with no provider package or key (mirrors the seam's own test pattern).
    """
    from langchain.chat_models import init_chat_model

    from ai_services.llm import make_chat_model

    inner = base_init or init_chat_model
    recorder = MeteringCallback(meter)

    def init(model: str, **kwargs: Any) -> BaseChatModel:
        callbacks = list(kwargs.pop("callbacks", None) or [])
        return inner(model, callbacks=[*callbacks, recorder], **kwargs)

    def make(purpose) -> BaseChatModel:
        return make_chat_model(purpose, init=init)

    return make


@contextmanager
def seam_env(overrides: dict[str, str]) -> Iterator[None]:
    """Temporarily apply model-routing env vars (and restore on exit).

    This is how a run points the production seam at the model under test —
    the same env contract docker-compose passes in a real deploy.
    """
    previous: dict[str, str | None] = {k: os.environ.get(k) for k in overrides}
    os.environ.update(overrides)
    try:
        yield
    finally:
        for key, old in previous.items():
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old
