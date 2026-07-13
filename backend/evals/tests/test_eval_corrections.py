"""Regression tests for eval costing and reporting corrections."""

import json
from pathlib import Path

import pytest

from bank.upload_extraction import costing
from bank.upload_extraction.costing import price_llm_tokens
from bank.upload_extraction.live_eval import (
    LiveUploadEvalConfig,
    UploadExtractionEvalRun,
)
from evals.metering import Meter
from evals.registry import get_model
from evals.report import reprice
from evals.scenarios.base import EvalUnit, new_record, settle_record


def test_live_costing_resolves_production_model_name():
    cost = price_llm_tokens(
        provider="openrouter",
        model="google/gemini-3.5-flash",
        input_tokens=10_500,
        output_tokens=5_000,
    )
    assert cost == pytest.approx(0.06075)


def test_settled_record_includes_ocr_pages():
    spec = get_model("google/gemini-3.5-flash")
    unit = EvalUnit("extraction", "ocr_mistral", spec.eval_id, {})
    record = new_record(unit, spec)
    meter = Meter(spec.model)
    meter.record_ocr(pages=25, latency_ms=10, model="mistral-ocr")

    settle_record(record, meter, spec)

    assert record.cost_usd == pytest.approx(0.10)


def test_report_marks_unknown_models_unpriced_but_keeps_free_arm_free():
    base = {
        "model_eval_id": "custom/not-registered",
        "input_tokens": 100,
        "output_tokens": 100,
        "cache_read_tokens": 0,
        "ocr_pages": 0,
    }
    assert reprice(base) is None
    assert reprice({**base, "model_eval_id": "none"}) == 0.0


def test_openrouter_pricing_retries_after_transient_failure(monkeypatch):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps(
                {
                    "data": [
                        {
                            "id": "vendor/model",
                            "pricing": {"prompt": "0.1", "completion": "0.2"},
                        }
                    ]
                }
            ).encode()

    attempts = iter([OSError("offline"), Response()])

    def fake_urlopen(*args, **kwargs):
        result = next(attempts)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(costing.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(costing, "_OPENROUTER_PRICING_CACHE", None)

    assert costing._openrouter_pricing() == {}
    assert "vendor/model" in costing._openrouter_pricing()


def test_ocr_cache_is_bound_to_pdf_hash_and_model(tmp_path, monkeypatch):
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"first-pdf")
    out = tmp_path / "run"
    out.mkdir()
    calls = []

    class FakeOcrClient:
        def __init__(self, *, model):
            self.model = model

        def process_pdf(self, pdf_bytes):
            calls.append((self.model, pdf_bytes))
            return {"pages": [{"index": 0, "markdown": "1. Question?"}]}

    monkeypatch.setattr("bank.upload_extraction.live_eval.count_pages", lambda _: 1)
    monkeypatch.setattr(
        "bank.upload_extraction.live_eval.MistralOcrClient", FakeOcrClient
    )

    def load(model: str):
        config = LiveUploadEvalConfig(
            pdf_path=Path(pdf),
            provider="gemini",
            models=[],
            batch_sizes=[],
            out_dir=out,
            ocr_model=model,
        )
        return UploadExtractionEvalRun(config).load_or_run_ocr()

    load("ocr-a")
    load("ocr-a")
    assert len(calls) == 1

    pdf.write_bytes(b"second-pdf")
    load("ocr-a")
    load("ocr-b")
    assert len(calls) == 3
