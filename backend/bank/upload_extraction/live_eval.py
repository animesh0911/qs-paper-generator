"""Live upload OCR + LLM extraction eval API.

This module is intentionally importable from external scripts. It exercises the
same upload-extraction module production uses, but does not create an
``IngestionJob`` or persist ``Question`` rows:

    PDF -> Mistral OCR -> OCR markdown batches -> extraction LLM -> questions

OCR is cached per run directory so a research matrix can vary LLM models and
batch sizes without re-billing OCR for every cell. Costs are still reported as
*per real upload run* costs: cached eval reuse does not zero out OCR cost.
"""

from __future__ import annotations

import csv
import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ai_services.llm import ModelPurpose
from bank.extraction import count_pages
from bank.ocr_extractor import MistralOcrClient, pages_from_ocr_response
from bank.upload_extraction.costing import price_llm_tokens, price_ocr_pages, total_cost
from bank.upload_extraction.pipeline import (
    BatchSize,
    FilterPolicy,
    UploadExtractionPipeline,
)
from evals.metering import Meter, metered_make_model, seam_env
from evals.registry import to_inr

_SIMPLE_COLUMNS = [
    "pdf_pages",
    "ocr_model",
    "ocr_cost",
    "ocr_latency",
    "ocr_output_size",
    "llm_model",
    "batch_size",
    "llm_cost",
    "llm_latency",
    "total_cost",
    "questions",
]


@dataclass(frozen=True)
class LiveUploadEvalConfig:
    """Interface for one live upload extraction eval matrix."""

    pdf_path: Path
    provider: str
    models: list[str]
    batch_sizes: list[BatchSize]
    out_dir: Path
    ocr_model: str | None = None
    ocr_usd_per_1000_pages: float | None = 1.0
    reuse_ocr: bool = True
    filter_policy: FilterPolicy = "english-question"
    max_batches: int = 0


@dataclass(frozen=True)
class LiveUploadEvalRow:
    """One simple report row for a model × batch-size cell."""

    pdf_pages: int
    ocr_model: str
    ocr_cost: float | None
    ocr_latency: int
    ocr_output_size: int
    llm_model: str
    batch_size: str
    llm_cost: float | None
    llm_latency: int
    total_cost: float | None
    questions: int

    # Extra diagnostics kept in JSON, not CSV, so the user-facing report stays
    # small while external tooling can still inspect the run.
    provider: str
    llm_calls: int
    llm_input_tokens: int
    llm_output_tokens: int
    selected_ocr_pages: int
    error: str = ""

    def simple_csv_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return {key: data[key] for key in _SIMPLE_COLUMNS}


@dataclass(frozen=True)
class CachedOcrRun:
    raw: dict[str, Any]
    pages: list[dict[str, Any]]
    pdf_pages: int
    model: str
    latency_ms: int
    output_chars: int
    cost_usd: float | None


class UploadExtractionEvalRun:
    """Deep live eval module for upload OCR + LLM costing.

    Interface: a config in, simple rows and artifacts out. The implementation
    owns OCR caching, LLM routing, metering, artifact writing, and CSV/JSONL
    reporting. External scripts stay thin adapters.
    """

    def __init__(self, config: LiveUploadEvalConfig):
        self.config = config

    def run(self) -> list[LiveUploadEvalRow]:
        cfg = self.config
        cfg.out_dir.mkdir(parents=True, exist_ok=True)
        ocr = self.load_or_run_ocr()
        self.write_ocr_markdown(ocr)

        rows: list[LiveUploadEvalRow] = []
        for model in cfg.models:
            for batch_size in cfg.batch_sizes:
                row = self.structure_cell(ocr=ocr, model=model, batch_size=batch_size)
                rows.append(row)
                self.append_csv([row])
                self.write_jsonl([asdict(row)])
        return rows

    def load_or_run_ocr(self) -> CachedOcrRun:
        """Return cached or freshly paid Mistral OCR output for the PDF."""
        cfg = self.config
        pdf_path = cfg.pdf_path.resolve()
        pdf_bytes = pdf_path.read_bytes()
        pdf_pages = count_pages(pdf_bytes)
        model = cfg.ocr_model or os.getenv("MISTRAL_OCR_MODEL") or "mistral-ocr-latest"
        ocr_path = cfg.out_dir / "ocr.json"
        meta_path = cfg.out_dir / "ocr_meta.json"

        latency_ms = 0
        if cfg.reuse_ocr and ocr_path.is_file():
            raw = json.loads(ocr_path.read_text(encoding="utf-8"))
            if meta_path.is_file():
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                latency_ms = int(meta.get("latency_ms") or 0)
                model = str(meta.get("model") or model)
                pdf_pages = int(meta.get("pdf_pages") or pdf_pages)
        else:
            started = time.monotonic()
            raw = MistralOcrClient(model=model).process_pdf(pdf_bytes)
            latency_ms = int((time.monotonic() - started) * 1000)
            ocr_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), "utf-8")
            meta_path.write_text(
                json.dumps(
                    {"model": model, "latency_ms": latency_ms, "pdf_pages": pdf_pages},
                    indent=2,
                ),
                "utf-8",
            )

        pages = pages_from_ocr_response(raw)
        output_chars = sum(len(page.get("markdown") or "") for page in pages)
        return CachedOcrRun(
            raw=raw,
            pages=pages,
            pdf_pages=pdf_pages,
            model=model,
            latency_ms=latency_ms,
            output_chars=output_chars,
            cost_usd=price_ocr_pages(
                pdf_pages, usd_per_1000_pages=cfg.ocr_usd_per_1000_pages
            ),
        )

    def structure_cell(
        self, *, ocr: CachedOcrRun, model: str, batch_size: BatchSize
    ) -> LiveUploadEvalRow:
        """Run one structuring model/batch cell against cached OCR markdown."""
        cfg = self.config
        meter = Meter(model)
        run = None
        started = time.monotonic()
        error = ""
        try:
            with seam_env(
                {
                    "LLM_EXTRACTION_PROVIDER": cfg.provider,
                    "LLM_EXTRACTION_MODEL": model,
                }
            ):
                chat_model = metered_make_model(meter)(ModelPurpose.EXTRACTION)
                pipeline = UploadExtractionPipeline(chat_model)
                run = pipeline.structure_pages(
                    pages=pipeline.coerce_ocr_pages(ocr.pages),
                    batch_size=batch_size,
                    filter_policy=cfg.filter_policy,
                    max_batches=cfg.max_batches,
                )
            questions = run.questions
        except Exception as exc:  # noqa: BLE001 - a failed model cell is a result
            questions = []
            error = f"{type(exc).__name__}: {exc}"
        latency_ms = int((time.monotonic() - started) * 1000)

        artifact_dir = (
            cfg.out_dir / "artifacts" / _safe_name(model) / f"batch-{batch_size}"
        )
        artifact_dir.mkdir(parents=True, exist_ok=True)
        (artifact_dir / "structured_batches.json").write_text(
            json.dumps(
                [batch.as_artifact() for batch in run.batches] if run else [],
                ensure_ascii=False,
                indent=2,
            ),
            "utf-8",
        )
        (artifact_dir / "questions.json").write_text(
            json.dumps(questions, ensure_ascii=False, indent=2), "utf-8"
        )

        llm_cost = price_llm_tokens(
            provider=cfg.provider,
            model=model,
            input_tokens=meter.input_tokens,
            output_tokens=meter.output_tokens,
            cache_read_tokens=meter.cache_read_tokens,
        )
        return LiveUploadEvalRow(
            pdf_pages=ocr.pdf_pages,
            ocr_model=ocr.model,
            ocr_cost=ocr.cost_usd,
            ocr_latency=ocr.latency_ms,
            ocr_output_size=ocr.output_chars,
            llm_model=model,
            batch_size=str(batch_size),
            llm_cost=llm_cost,
            llm_latency=latency_ms,
            total_cost=total_cost(llm_cost, ocr.cost_usd),
            questions=len(questions),
            provider=cfg.provider,
            llm_calls=len([call for call in meter.calls if call.kind == "chat"]),
            llm_input_tokens=meter.input_tokens,
            llm_output_tokens=meter.output_tokens,
            selected_ocr_pages=len(run.selected_pages) if run else 0,
            error=error,
        )

    def append_csv(self, rows: list[LiveUploadEvalRow]) -> None:
        path = self.config.out_dir / "results.csv"
        exists = path.is_file()
        with path.open("a", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=_SIMPLE_COLUMNS)
            if not exists:
                writer.writeheader()
            for row in rows:
                writer.writerow(_format_simple_row(row.simple_csv_dict()))

    def write_jsonl(self, rows: list[dict[str, Any]]) -> None:
        path = self.config.out_dir / "results.jsonl"
        with path.open("a", encoding="utf-8") as fh:
            for row in rows:
                row = dict(row)
                if row.get("total_cost") is not None:
                    row["total_cost_inr"] = to_inr(row["total_cost"])
                fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    def write_ocr_markdown(self, ocr: CachedOcrRun) -> None:
        (self.config.out_dir / "ocr.md").write_text(
            "\n\n--- OCR PAGE ---\n\n".join(
                str(page.get("markdown") or "") for page in ocr.pages
            ),
            encoding="utf-8",
        )


def run_live_upload_extraction_eval(
    *,
    pdf_path: Path,
    provider: str,
    models: list[str],
    batch_sizes: list[BatchSize],
    out_dir: Path,
    ocr_model: str | None = None,
    ocr_usd_per_1000_pages: float | None = 1.0,
    reuse_ocr: bool = True,
    filter_policy: FilterPolicy = "english-question",
    max_batches: int = 0,
) -> list[LiveUploadEvalRow]:
    """Compatibility function used by external scripts."""
    return UploadExtractionEvalRun(
        LiveUploadEvalConfig(
            pdf_path=pdf_path,
            provider=provider,
            models=models,
            batch_sizes=batch_sizes,
            out_dir=out_dir,
            ocr_model=ocr_model,
            ocr_usd_per_1000_pages=ocr_usd_per_1000_pages,
            reuse_ocr=reuse_ocr,
            filter_policy=filter_policy,
            max_batches=max_batches,
        )
    ).run()


def _format_simple_row(row: dict[str, Any]) -> dict[str, Any]:
    formatted = dict(row)
    for key in ("ocr_cost", "llm_cost", "total_cost"):
        value = formatted.get(key)
        formatted[key] = "" if value is None else f"{value:.6f}"
    return formatted


def _safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in value)
