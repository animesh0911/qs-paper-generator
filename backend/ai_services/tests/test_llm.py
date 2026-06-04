"""Tests for the Gemini native-PDF LLM gateway.

`GeminiClient.extract` is exercised through an injected `generate_func`, so the
suite never imports google-genai or hits the network.
"""

from __future__ import annotations

import json

from ai_services.llm import (
    _DEFAULT_THINKING_BUDGET,
    GeminiClient,
    _thinking_budget,
    make_llm_client,
)


def test_extract_sends_pdf_prompt_schema_and_parses_json():
    """extract passes the PDF + prompt + schema through and returns parsed JSON.

    Why this matters: this is the seam every section call goes through. If the
    arg contract or JSON parsing drifts, every ingested paper breaks."""
    calls = []

    def fake_generate(**kwargs):
        calls.append(kwargs)
        return json.dumps({"questions": [{"section": "A", "rawText": "Q?"}]})

    schema = {"type": "OBJECT"}
    client = GeminiClient(
        model="gemini-3.5-flash", generate_func=fake_generate, timeout=12
    )

    result = client.extract(b"%PDF-bytes", "extract section A", schema)

    assert result == {"questions": [{"section": "A", "rawText": "Q?"}]}
    assert len(calls) == 1
    call = calls[0]
    assert call["model"] == "gemini-3.5-flash"
    assert call["pdf_bytes"] == b"%PDF-bytes"
    assert call["prompt"] == "extract section A"
    assert call["response_schema"] is schema
    assert call["timeout"] == 12


def test_generate_text_sends_prompt_schema_and_parses_json():
    """generate_text passes the prompt + schema through (no PDF) and parses JSON.

    Why this matters: answer generation rides this seam. If the arg contract or
    JSON parsing drifts, every generated answer breaks."""
    calls = []

    def fake_generate_text(**kwargs):
        calls.append(kwargs)
        return json.dumps({"answer": "Oxygen."})

    schema = {"type": "OBJECT"}
    client = GeminiClient(
        model="gemini-3.5-flash",
        generate_text_func=fake_generate_text,
        timeout=12,
    )

    result = client.generate_text("answer this question", schema)

    assert result == {"answer": "Oxygen."}
    assert len(calls) == 1
    call = calls[0]
    assert call["model"] == "gemini-3.5-flash"
    assert call["prompt"] == "answer this question"
    assert call["response_schema"] is schema
    assert call["timeout"] == 12
    assert "pdf_bytes" not in call


def test_model_defaults_to_gemini_3_5_flash(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    client = GeminiClient(generate_func=lambda **kw: "{}")
    assert client.model == "gemini-3.5-flash"


def test_model_from_env(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.1-pro-preview")
    client = GeminiClient(generate_func=lambda **kw: "{}")
    assert client.model == "gemini-3.1-pro-preview"


def test_make_llm_client_returns_gemini_client():
    assert isinstance(make_llm_client(), GeminiClient)


def test_thinking_budget_defaults_to_dynamic(monkeypatch):
    monkeypatch.delenv("GEMINI_THINKING_BUDGET", raising=False)
    assert _thinking_budget() == _DEFAULT_THINKING_BUDGET == -1


def test_thinking_budget_from_env(monkeypatch):
    monkeypatch.setenv("GEMINI_THINKING_BUDGET", "0")  # thinking off
    assert _thinking_budget() == 0


def test_thinking_budget_invalid_env_falls_back(monkeypatch):
    """A non-integer env value falls back to the default, not a crash."""
    monkeypatch.setenv("GEMINI_THINKING_BUDGET", "lots")
    assert _thinking_budget() == _DEFAULT_THINKING_BUDGET
