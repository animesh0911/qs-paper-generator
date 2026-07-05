"""Teacher-facing sanitisation of raw LLM-provider errors.

Provider SDKs (OpenAI / OpenRouter / Anthropic / …) raise errors whose ``str()``
is a full JSON dump: the HTTP code plus nested metadata, the account ``user_id``,
billing URLs, and previous-error chains. That must never reach a teacher's
screen — it leaks internals, carries account identifiers, and reads like a
crash. ``friendly_llm_error`` maps the common provider failures to one short,
actionable sentence and drops the raw payload. Unknown or plain domain errors
fall back to a compact, length-bounded ``Type: message`` (so short messages like
``"model unavailable"`` survive), while the raw text stays in the worker logs
for operators.
"""

from __future__ import annotations

import re

_ERROR_CODE_RE = re.compile(r"[Ee]rror code:\s*(\d{3})")
_MAX_FALLBACK_LEN = 300


def _message_for_code(code: int) -> str | None:
    if code in (401, 403):
        return (
            "The AI provider rejected the request (authentication). An "
            "administrator needs to check the provider API key."
        )
    if code == 402:
        return (
            "The AI provider is out of credits, or the request is larger than "
            "the remaining quota. Add credits or reduce the request, then retry."
        )
    if code == 429:
        return (
            "The AI provider is rate-limiting requests right now. Wait a moment "
            "and retry."
        )
    if code == 400:
        return (
            "The AI provider rejected the request as invalid. Please retry; if "
            "it keeps failing, contact support."
        )
    if 500 <= code <= 599:
        return (
            "The AI provider had a temporary server error. Please retry in a " "moment."
        )
    return None


def friendly_llm_error(exc: Exception | str) -> str:
    """Return a short, teacher-safe message for a provider error.

    Never includes the raw provider JSON (which can carry account ids, billing
    URLs, and internal metadata). Known HTTP failures map to actionable copy;
    anything else falls back to a compact, length-bounded ``Type: message``.
    """
    raw = str(exc)
    match = _ERROR_CODE_RE.search(raw)
    if match:
        code = int(match.group(1))
        mapped = _message_for_code(code)
        if mapped:
            return mapped
        return (
            f"The AI provider returned an error (code {code}). Please retry, or "
            "contact support if it keeps failing."
        )

    if isinstance(exc, Exception):
        compact = f"{type(exc).__name__}: {raw.strip() or 'unknown error'}"
    else:
        compact = raw.strip() or "Unknown error"
    if len(compact) > _MAX_FALLBACK_LEN:
        compact = compact[: _MAX_FALLBACK_LEN - 1].rstrip() + "…"
    return compact
