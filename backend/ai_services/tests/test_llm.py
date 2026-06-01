"""Tests for the shared LiteLLM gateway."""

from __future__ import annotations

from types import SimpleNamespace

from ai_services.llm import LiteLLMClient, configured_model, provider_model


def test_configured_model_prefers_litellm_model_env(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "openai/gpt-5-mini")
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")

    assert configured_model() == "openai/gpt-5-mini"


def test_configured_model_supports_legacy_provider_env(monkeypatch):
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-flash")

    assert configured_model() == "gemini/gemini-2.5-flash"


def test_provider_model_does_not_double_prefix():
    assert provider_model("openai", "openai/gpt-5-mini") == "openai/gpt-5-mini"
    assert provider_model("openai", "gpt-5-mini") == "openai/gpt-5-mini"


def test_litellm_client_sends_openai_style_messages_and_returns_text():
    calls = []

    def fake_completion(**kwargs):
        calls.append(kwargs)
        return {
            "choices": [
                {"message": {"content": "Tagged successfully."}},
            ],
        }

    client = LiteLLMClient(
        model="anthropic/claude-haiku-4-5-20251001",
        completion_func=fake_completion,
        timeout=12,
    )

    result = client.complete("tag this", max_tokens=123)

    assert result == "Tagged successfully."
    assert calls == [
        {
            "model": "anthropic/claude-haiku-4-5-20251001",
            "messages": [{"role": "user", "content": "tag this"}],
            "max_tokens": 123,
            "timeout": 12,
        }
    ]


def test_litellm_client_supports_object_style_response():
    def fake_completion(**_kwargs):
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content="Object response works."),
                )
            ]
        )

    client = LiteLLMClient(
        model="openai/gpt-5-mini",
        completion_func=fake_completion,
    )

    assert client.complete("hello") == "Object response works."
