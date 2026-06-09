"""Tests for the shared LLM module: the native-PDF extraction adapter and the
provider-agnostic model seam.

The extraction adapter is exercised through an injected ``generate_func`` and the
seam through an injected ``init``/a ``GenericFakeChatModel``, so the suite never
imports a provider integration or hits the network.
"""

from __future__ import annotations

import json
import logging

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from ai_services.llm import (
    _DEFAULT_THINKING_BUDGET,
    ChatModelConfig,
    GeminiClient,
    LlmCallObserver,
    ModelPurpose,
    _thinking_budget,
    make_chat_model,
    make_llm_client,
    resolve_chat_model_config,
)

# ---------------------------------------------------------------------------
# Native-PDF extraction adapter (ADR-0004) — stays on the bespoke google-genai
# path, off the seam.
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Model seam (ADR-0005) — provider/model/key/retry resolved in one place so
# call sites are provider-blind.
# ---------------------------------------------------------------------------

_SEAM_ENV = [
    "LLM_PROVIDER",
    "LLM_MAX_RETRIES",
    "GEMINI_MODEL",
    "GEMINI_API_KEY",
    "ANTHROPIC_MODEL",
    "ANTHROPIC_API_KEY",
    "OPENAI_MODEL",
    "OPENAI_API_KEY",
    "OLLAMA_MODEL",
    "LLM_ANSWER_GENERATION_PROVIDER",
    "LLM_ANSWER_GENERATION_MODEL",
    "LLM_EXTRACTION_PROVIDER",
    "LLM_EXTRACTION_MODEL",
]


@pytest.fixture
def clean_llm_env(monkeypatch):
    """Strip every env var the seam reads so config resolution is hermetic
    regardless of what the container/compose injected."""
    for key in _SEAM_ENV:
        monkeypatch.delenv(key, raising=False)
    return monkeypatch


def test_config_defaults_to_gemini_extraction_model(clean_llm_env):
    """With nothing configured the seam defaults to Gemini on the same model as
    extraction — answer generation rides the existing provider, not a surprise
    one. Why this matters: a wrong default silently changes who gets billed."""
    cfg = resolve_chat_model_config(ModelPurpose.ANSWER_GENERATION)
    assert cfg.provider == "google_genai"
    assert cfg.model == "gemini-3.5-flash"
    assert cfg.init_kwargs["max_retries"] == 2


def test_config_extraction_defaults_to_gemini_extraction_model(clean_llm_env):
    """Extraction rode the bespoke native-PDF path until #156 put it on the seam;
    with nothing configured it must resolve to the SAME Gemini model the bespoke
    path used (gemini-3.5-flash) — a different default would silently change which
    model (and bill) ingestion hits."""
    cfg = resolve_chat_model_config(ModelPurpose.EXTRACTION)
    assert cfg.provider == "google_genai"
    assert cfg.model == "gemini-3.5-flash"


def test_config_extraction_swaps_provider_independently(clean_llm_env):
    """LLM_EXTRACTION_* moves extraction to another provider without touching the
    call site or other purposes — the seam's promise applied to ingestion (#134:
    a local model could replace Gemini extraction by config alone)."""
    clean_llm_env.setenv("LLM_EXTRACTION_PROVIDER", "ollama")
    clean_llm_env.setenv("LLM_EXTRACTION_MODEL", "chandra-ocr-2")

    cfg = resolve_chat_model_config(ModelPurpose.EXTRACTION)

    assert cfg.provider == "ollama"
    assert cfg.model == "chandra-ocr-2"
    assert "api_key" not in cfg.init_kwargs  # local model needs no key


def test_config_swaps_provider_by_env(clean_llm_env):
    """LLM_PROVIDER swaps the provider without any call site changing — the whole
    point of the seam (ADR-0005)."""
    clean_llm_env.setenv("LLM_PROVIDER", "anthropic")
    clean_llm_env.setenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
    clean_llm_env.setenv("ANTHROPIC_API_KEY", "sk-test")

    cfg = resolve_chat_model_config(ModelPurpose.ANSWER_GENERATION)

    assert cfg.provider == "anthropic"
    assert cfg.model == "claude-sonnet-4-6"
    assert cfg.init_kwargs["api_key"] == "sk-test"


def test_config_swaps_to_local_provider(clean_llm_env):
    """A local-capable provider (ollama) swaps in by config with no API key —
    proving the seam isn't tied to a hosted vendor (#134)."""
    clean_llm_env.setenv("LLM_PROVIDER", "ollama")
    clean_llm_env.setenv("OLLAMA_MODEL", "llama3.2")

    cfg = resolve_chat_model_config(ModelPurpose.ANSWER_GENERATION)

    assert cfg.provider == "ollama"
    assert cfg.model == "llama3.2"
    assert "api_key" not in cfg.init_kwargs  # local model needs no key


def test_config_purpose_override_beats_global(clean_llm_env):
    """A purpose-specific override wins over the global default, so one surface
    can move providers without dragging the others."""
    clean_llm_env.setenv("LLM_PROVIDER", "gemini")
    clean_llm_env.setenv("LLM_ANSWER_GENERATION_PROVIDER", "anthropic")
    clean_llm_env.setenv("LLM_ANSWER_GENERATION_MODEL", "claude-haiku-4-5")

    cfg = resolve_chat_model_config(ModelPurpose.ANSWER_GENERATION)

    assert cfg.provider == "anthropic"
    assert cfg.model == "claude-haiku-4-5"


def test_config_unknown_provider_fails_loud(clean_llm_env):
    clean_llm_env.setenv("LLM_PROVIDER", "wishful")
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        resolve_chat_model_config(ModelPurpose.ANSWER_GENERATION)


def test_config_missing_model_fails_loud(clean_llm_env):
    """A provider with no built-in default and no <PREFIX>_MODEL must fail loud,
    not silently construct an unintended model (Rule 12)."""
    clean_llm_env.setenv("LLM_PROVIDER", "anthropic")  # no default model
    with pytest.raises(ValueError, match="No model configured"):
        resolve_chat_model_config(ModelPurpose.ANSWER_GENERATION)


def test_make_chat_model_builds_from_config_and_attaches_observer(clean_llm_env):
    """make_chat_model hands the resolved config to init_chat_model and attaches
    the seam observer — that wiring is what makes every call observable."""
    captured = {}

    def fake_init(model, **kwargs):
        captured["model"] = model
        captured["kwargs"] = kwargs
        return GenericFakeChatModel(messages=iter([AIMessage(content="ok")]))

    make_chat_model(ModelPurpose.ANSWER_GENERATION, init=fake_init)

    assert captured["model"] == "gemini-3.5-flash"
    assert captured["kwargs"]["model_provider"] == "google_genai"
    assert captured["kwargs"]["max_retries"] == 2
    callbacks = captured["kwargs"]["callbacks"]
    assert any(isinstance(cb, LlmCallObserver) for cb in callbacks)


@pytest.mark.parametrize(
    "provider,model,key_env,expected_cls",
    [
        ("anthropic", "claude-haiku-4-5", "ANTHROPIC_API_KEY", "ChatAnthropic"),
        ("ollama", "llama3.2", None, "ChatOllama"),  # local-capable, no API key
    ],
)
def test_make_chat_model_constructs_swapped_provider(
    clean_llm_env, provider, model, key_env, expected_cls
):
    """Real construction (no invoke, so no API call) for a swapped provider.

    Why this matters: this is the acceptance criterion "swappable... verified
    with at least two providers, one local-capable". A config-only test would
    pass even if the integration package were missing — the swap would then be a
    lie that only surfaces as an ImportError at runtime. Building the real model
    here proves the dependency is installed and the seam wires it up.
    """
    clean_llm_env.setenv("LLM_PROVIDER", provider)
    clean_llm_env.setenv(f"{provider.upper()}_MODEL", model)
    if key_env:
        clean_llm_env.setenv(key_env, "test-key-not-used")

    model_obj = make_chat_model(ModelPurpose.ANSWER_GENERATION)

    assert type(model_obj).__name__ == expected_cls


def test_observer_logs_latency_and_tokens_at_seam(caplog):
    """Every call through the seam emits one telemetry line. Why this matters:
    observability is the documented reason the seam exists (ADR-0005); a call
    that doesn't log is a blind spot for cost/latency."""
    model = GenericFakeChatModel(
        messages=iter([AIMessage(content="hi")]),
        callbacks=[LlmCallObserver(ModelPurpose.ANSWER_GENERATION)],
    )

    with caplog.at_level(logging.INFO, logger="ai_services.llm"):
        model.invoke("anything")

    records = [r for r in caplog.records if r.message.startswith("llm_call ")]
    assert len(records) == 1
    msg = records[0].getMessage()
    assert "purpose=answer_generation" in msg
    assert "latency_ms=" in msg
    # A fake model reports no usage; the observer must degrade to {} not crash.
    assert "tokens={}" in msg


def test_chat_model_config_is_immutable():
    """The resolved recipe is frozen so a caller can't mutate shared config."""
    cfg = ChatModelConfig(provider="google_genai", model="m", init_kwargs={})
    with pytest.raises(Exception):
        cfg.model = "other"  # type: ignore[misc]
