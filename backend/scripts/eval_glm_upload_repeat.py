#!/usr/bin/env python3
"""Fresh GLM-OCR -> Markdown -> structuring-model cost repeatability run."""
from __future__ import annotations

import argparse
import base64
import json
import os
import shlex
import sys
import time
import httpx
from pathlib import Path
from typing import Any
from uuid import uuid4

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

DEFAULT_MODELS = ["google/gemini-3-flash-preview", "google/gemini-2.5-flash"]
GLM_INPUT_USD_PER_M = 0.03
GLM_OUTPUT_USD_PER_M = 0.03
FX_INR_PER_USD = 95.3361


def load_env() -> None:
    for path in (REPO / ".env", BACKEND / ".env"):
        if not path.is_file():
            continue
        for line in path.read_text().splitlines():
            try:
                parts = shlex.split(line, comments=True, posix=True)
            except ValueError:
                continue
            if len(parts) == 1 and "=" in parts[0]:
                key, value = parts[0].split("=", 1)
                os.environ.setdefault(key.strip(), value)


def request_json(
    url: str,
    payload: dict[str, Any],
    key: str,
    *,
    timeout: int = 900,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, Any]]:
    try:
        response = httpx.post(
            url,
            json=payload,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                **(headers or {}),
            },
            timeout=httpx.Timeout(timeout),
        )
        try:
            body = response.json()
        except ValueError:
            body = {"error": {"http_status": response.status_code, "body": response.text}}
        return response.status_code, body
    except Exception as exc:  # noqa: BLE001
        return 0, {"error": {"type": type(exc).__name__, "message": str(exc)}}


def safe_name(model: str) -> str:
    return model.replace("/", "__").replace(":", "_")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--models", default=",".join(DEFAULT_MODELS))
    parser.add_argument(
        "--glm-region", choices=("china", "international"), default="china"
    )
    parser.add_argument("--ocr-only", action="store_true")
    args = parser.parse_args()
    if not args.pdf.is_file():
        raise SystemExit(f"PDF not found: {args.pdf}")

    load_env()
    args.out.mkdir(parents=True, exist_ok=True)
    import django

    django.setup()
    import fitz

    from bank.extraction import build_question_schema, genai_to_json_schema, merge_page_payloads
    from bank.ocr_extractor import _POC_CHAPTER_SLUGS, _drop_visual_questions
    from bank.question_shape import compute_parse_quality
    from scripts.eval_glm_markdown_llms import prompt

    pdf_bytes = args.pdf.read_bytes()
    with fitz.open(stream=pdf_bytes, filetype="pdf") as pdf_document:
        pdf_pages = pdf_document.page_count
    pdf_b64 = base64.b64encode(pdf_bytes).decode()
    ocr_request_id = f"qs-glm-ocr-{uuid4().hex}"
    ocr_request = {
        "model": "glm-ocr",
        "file": f"data:application/pdf;base64,{pdf_b64}",
        "return_crop_images": False,
        "need_layout_visualization": False,
        "request_id": ocr_request_id,
    }
    # The request artifact records metadata only; never duplicate a multi-MB PDF as base64.
    (args.out / "ocr-request.json").write_text(
        json.dumps(
            {
                "model": "glm-ocr",
                "source_pdf": str(args.pdf),
                "pdf_bytes": len(pdf_bytes),
                "pdf_pages": pdf_pages,
                "return_crop_images": False,
                "need_layout_visualization": False,
                "request_id": ocr_request_id,
                "endpoint": (
                    "https://open.bigmodel.cn/api/paas/v4/layout_parsing"
                    if args.glm_region == "china"
                    else "https://api.z.ai/api/paas/v4/layout_parsing"
                ),
                "client": (
                    "zai-sdk==0.2.3 ZhipuAiClient"
                    if args.glm_region == "china"
                    else "zai-sdk==0.2.3 ZaiClient"
                ),
                "implicit_retries": 0,
            },
            indent=2,
        )
    )
    # Use Zhipu's documented China-region SDK rather than a custom HTTP client.
    # No implicit retries keeps this paid measurement attributable to one request.
    from zai import ZaiClient, ZhipuAiClient

    client_class = ZhipuAiClient if args.glm_region == "china" else ZaiClient
    started = time.monotonic()
    try:
        with client_class(
            api_key=os.environ["ZAI_API_KEY"],
            timeout=httpx.Timeout(1200, connect=30, write=1200, read=1200),
            max_retries=0,
        ) as client:
            ocr_result = client.layout_parsing.create(**ocr_request)
        ocr_status = 200
        ocr_response = ocr_result.model_dump(mode="json")
    except Exception as exc:  # noqa: BLE001
        ocr_status = 0
        cause = exc.__cause__
        ocr_response = {
            "error": {
                "type": type(exc).__name__,
                "message": str(exc),
                "repr": repr(exc),
                "cause_type": type(cause).__name__ if cause else None,
                "cause": repr(cause) if cause else None,
            }
        }
    ocr_latency_ms = int((time.monotonic() - started) * 1000)
    (args.out / "ocr-response.json").write_text(
        json.dumps(ocr_response, ensure_ascii=False, indent=2)
    )
    if ocr_status != 200 or ocr_response.get("error"):
        raise SystemExit(f"GLM-OCR failed HTTP {ocr_status}: {ocr_response.get('error')}")
    markdown = str(ocr_response.get("md_results") or "")
    (args.out / "ocr.md").write_text(markdown)
    ocr_usage = ocr_response.get("usage") or {}
    ocr_input = int(ocr_usage.get("prompt_tokens") or 0)
    ocr_output = int(ocr_usage.get("completion_tokens") or 0)
    ocr_cost = (
        ocr_input * GLM_INPUT_USD_PER_M + ocr_output * GLM_OUTPUT_USD_PER_M
    ) / 1_000_000
    ocr_summary = {
        "source_pdf": str(args.pdf),
        "pdf_bytes": len(pdf_bytes),
        "pdf_mb": len(pdf_bytes) / 1_000_000,
        "pdf_mib": len(pdf_bytes) / 1024 / 1024,
        "pdf_pages": pdf_pages,
        "http_status": ocr_status,
        "latency_ms": ocr_latency_ms,
        "markdown_chars": len(markdown),
        "prompt_tokens": ocr_input,
        "completion_tokens": ocr_output,
        "total_tokens": int(ocr_usage.get("total_tokens") or ocr_input + ocr_output),
        "pricing_usd_per_m_input": GLM_INPUT_USD_PER_M,
        "pricing_usd_per_m_output": GLM_OUTPUT_USD_PER_M,
        "ocr_cost_usd": ocr_cost,
        "ocr_cost_inr": ocr_cost * FX_INR_PER_USD,
    }
    (args.out / "ocr-summary.json").write_text(json.dumps(ocr_summary, indent=2))
    print(json.dumps({"stage": "ocr", **ocr_summary}), flush=True)
    if args.ocr_only:
        return 0

    schema = build_question_schema(_POC_CHAPTER_SLUGS)
    json_schema = genai_to_json_schema(schema)
    text = prompt(markdown, schema)
    rows: list[dict[str, Any]] = []
    for model in [item.strip() for item in args.models.split(",") if item.strip()]:
        model_dir = args.out / "models" / safe_name(model)
        model_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": text}],
            "temperature": 0,
            "max_tokens": 30000,
            "reasoning": {"enabled": False},
            "usage": {"include": True},
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "cbse_questions",
                    "strict": True,
                    "schema": json_schema,
                },
            },
        }
        (model_dir / "request.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2)
        )
        started = time.monotonic()
        status, response = request_json(
            "https://openrouter.ai/api/v1/chat/completions",
            payload,
            os.environ["OPENROUTER_API_KEY"],
            timeout=900,
            headers={
                "HTTP-Referer": "https://github.com/qs-paper-generator",
                "X-Title": "QS GLM Upload Repeatability Eval",
            },
        )
        latency_ms = int((time.monotonic() - started) * 1000)
        (model_dir / "response.json").write_text(
            json.dumps(response, ensure_ascii=False, indent=2)
        )
        usage = response.get("usage") or {}
        llm_cost = usage.get("cost")
        row: dict[str, Any] = {
            "model": model,
            "http_status": status,
            "latency_ms": latency_ms,
            "input_tokens": usage.get("prompt_tokens"),
            "output_tokens": usage.get("completion_tokens"),
            "llm_cost_usd": llm_cost,
            "llm_cost_inr": llm_cost * FX_INR_PER_USD if isinstance(llm_cost, (int, float)) else None,
            "ocr_cost_usd": ocr_cost,
            "complete_pipeline_cost_usd": llm_cost + ocr_cost if isinstance(llm_cost, (int, float)) else None,
            "complete_pipeline_cost_inr": (llm_cost + ocr_cost) * FX_INR_PER_USD if isinstance(llm_cost, (int, float)) else None,
            "complete_pipeline_latency_ms": latency_ms + ocr_latency_ms,
            "raw_entries": 0,
            "visual_removed": 0,
            "persistable_entries": 0,
            "clean": 0,
            "partial": 0,
            "broken": 0,
            "valid_json": False,
            "finish_reason": None,
            "error": "",
        }
        try:
            choice = response["choices"][0]
            row["finish_reason"] = choice.get("finish_reason")
            content = choice["message"]["content"]
            structured = json.loads(content) if isinstance(content, str) else content
            row["valid_json"] = True
            raw_count = len(structured.get("questions") or [])
            filtered = _drop_visual_questions(structured)
            filtered_count = len(filtered.get("questions") or [])
            questions = merge_page_payloads([filtered])
            qualities = [compute_parse_quality(q, q["qtype"]) for q in questions]
            row.update(
                {
                    "raw_entries": raw_count,
                    "visual_removed": raw_count - filtered_count,
                    "persistable_entries": len(questions),
                    "clean": qualities.count("clean"),
                    "partial": qualities.count("partial"),
                    "broken": qualities.count("broken"),
                }
            )
            (model_dir / "payload.json").write_text(
                json.dumps(structured, ensure_ascii=False, indent=2)
            )
            (model_dir / "questions.json").write_text(
                json.dumps(questions, ensure_ascii=False, indent=2)
            )
        except Exception as exc:  # noqa: BLE001
            row["error"] = f"{type(exc).__name__}: {exc}"
            if response.get("error"):
                row["error"] = json.dumps(response["error"], ensure_ascii=False)[:2000]
        (model_dir / "summary.json").write_text(json.dumps(row, indent=2))
        rows.append(row)
        (args.out / "results.json").write_text(json.dumps(rows, indent=2))
        print(json.dumps({"stage": "structuring", **row}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
