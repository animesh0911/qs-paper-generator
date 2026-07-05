"""Tests for teacher-facing LLM-provider error sanitisation."""

from __future__ import annotations

from ai_services.errors import friendly_llm_error


class APIStatusError(Exception):
    """Stand-in for a provider SDK error whose str() is a JSON dump."""


def test_402_credits_error_is_replaced_with_actionable_copy():
    raw = (
        "Error code: 402 - {'error': {'message': 'This request requires more "
        "credits, or fewer max_tokens. You requested up to 65536 tokens, but "
        "can only afford 64839. To increase, visit "
        "https://openrouter.ai/settings/credits and add more credits', 'code': "
        "402}, 'user_id': 'user_3AyQVHb1qunw7yHSFGBTrdtBBkr'}"
    )
    message = friendly_llm_error(APIStatusError(raw))

    assert "credits" in message.lower()
    # None of the raw payload leaks through.
    assert "user_id" not in message
    assert "user_3AyQVHb1qunw7yHSFGBTrdtBBkr" not in message
    assert "openrouter.ai" not in message
    assert "max_tokens" not in message
    assert "{" not in message


def test_common_http_codes_map_to_distinct_messages():
    assert "authentication" in friendly_llm_error("Error code: 401 - {...}").lower()
    assert "rate-limiting" in friendly_llm_error("Error code: 429 - {...}").lower()
    assert "server error" in friendly_llm_error("Error code: 503 - {...}").lower()


def test_unknown_code_is_generic_without_payload():
    message = friendly_llm_error("Error code: 418 - {'secret': 'leak'}")
    assert "418" in message
    assert "leak" not in message


def test_plain_domain_error_is_preserved_compactly():
    # Short, safe messages must survive so operators keep the signal.
    assert friendly_llm_error(RuntimeError("model unavailable")) == (
        "RuntimeError: model unavailable"
    )


def test_overlong_fallback_is_truncated():
    message = friendly_llm_error(RuntimeError("x" * 500))
    assert len(message) <= 300
    assert message.endswith("…")
