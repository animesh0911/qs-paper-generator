"""The metered factory records tokens/latency while riding the real seam.

Mirrors ai_services/tests/test_llm.py conventions: a ``GenericFakeChatModel``
through an injected init — no provider package, no key, no network.
"""

import os

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from ai_services.llm import ModelPurpose
from evals.metering import Meter, metered_make_model, seam_env


@pytest.fixture
def clean_llm_env(monkeypatch):
    for key in list(os.environ):
        if key.startswith(("LLM_", "GEMINI_", "DEEPSEEK_", "OPENROUTER_")):
            monkeypatch.delenv(key, raising=False)


def _fake_init_with_usage(**usage):
    message = AIMessage(content="ok", usage_metadata=usage or None)

    def fake_init(model, *, model_provider=None, callbacks=None, **kwargs):
        return GenericFakeChatModel(messages=iter([message]), callbacks=callbacks)

    return fake_init


def test_meter_records_one_call_with_usage_and_latency(clean_llm_env):
    meter = Meter("model-under-test")
    make = metered_make_model(
        meter,
        base_init=_fake_init_with_usage(
            input_tokens=120, output_tokens=45, total_tokens=165
        ),
    )
    make(ModelPurpose.QUESTION_GENERATION).invoke("hi")

    assert len(meter.calls) == 1
    call = meter.calls[0]
    assert call.kind == "chat"
    assert call.model == "model-under-test"
    assert (call.input_tokens, call.output_tokens) == (120, 45)
    assert call.latency_ms >= 0
    assert not call.error
    assert (meter.input_tokens, meter.output_tokens) == (120, 45)


def test_meter_survives_models_without_usage_metadata(clean_llm_env):
    meter = Meter("m")
    make = metered_make_model(meter, base_init=_fake_init_with_usage())
    make(ModelPurpose.EXTRACTION).invoke("hi")
    assert meter.calls[0].input_tokens == 0
    assert meter.calls[0].output_tokens == 0


def test_production_seam_still_resolves_routing_env(clean_llm_env, monkeypatch):
    """seam_env overrides drive the real resolve path the deploy would use."""
    seen: dict = {}

    def spy_init(model, *, model_provider=None, callbacks=None, **kwargs):
        seen["model"] = model
        seen["provider"] = model_provider
        return GenericFakeChatModel(
            messages=iter([AIMessage(content="ok")]), callbacks=callbacks
        )

    meter = Meter("m")
    overrides = {
        "LLM_ANSWER_GENERATION_PROVIDER": "deepseek",
        "LLM_ANSWER_GENERATION_MODEL": "deepseek-v4-flash",
    }
    with seam_env(overrides):
        make = metered_make_model(meter, base_init=spy_init)
        make(ModelPurpose.ANSWER_GENERATION).invoke("hi")

    assert seen == {"model": "deepseek-v4-flash", "provider": "openai"}
    assert "LLM_ANSWER_GENERATION_PROVIDER" not in os.environ


def test_ocr_calls_are_metered_by_page():
    meter = Meter("m")
    meter.record_ocr(pages=3, latency_ms=42, model="mistral-ocr")
    assert meter.ocr_pages == 3
    assert meter.calls[0].kind == "ocr"
