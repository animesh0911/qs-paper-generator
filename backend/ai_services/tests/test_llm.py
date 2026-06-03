"""Tests for the Gemini native-PDF LLM gateway.

`GeminiClient.extract` is exercised through an injected `generate_func`, so the
suite never imports google-genai or hits the network.
"""

from __future__ import annotations

import json

from ai_services.llm import GeminiClient, make_llm_client


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
        model="gemini-2.5-pro", generate_func=fake_generate, timeout=12
    )

    result = client.extract(b"%PDF-bytes", "extract section A", schema)

    assert result == {"questions": [{"section": "A", "rawText": "Q?"}]}
    assert len(calls) == 1
    call = calls[0]
    assert call["model"] == "gemini-2.5-pro"
    assert call["pdf_bytes"] == b"%PDF-bytes"
    assert call["prompt"] == "extract section A"
    assert call["response_schema"] is schema
    assert call["timeout"] == 12


def test_model_defaults_to_gemini_pro(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    client = GeminiClient(generate_func=lambda **kw: "{}")
    assert client.model == "gemini-2.5-pro"


def test_model_from_env(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-flash")
    client = GeminiClient(generate_func=lambda **kw: "{}")
    assert client.model == "gemini-2.5-flash"


def test_make_llm_client_returns_gemini_client():
    assert isinstance(make_llm_client(), GeminiClient)
