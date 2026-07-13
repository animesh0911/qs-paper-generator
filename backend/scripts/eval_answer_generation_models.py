#!/usr/bin/env python3
"""One-off OpenRouter comparison using the production answer prompt/parser.

Loads persisted questions for one completed ingestion, sends the exact prompt
built by ``bank.answer_generation_core``, records provider-returned cost and
latency, and saves outputs without writing answers back to the database.
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

DEFAULT_MODELS = [
    "google/gemini-2.5-flash-lite",
    "google/gemini-2.5-flash",
    "google/gemini-3-flash-preview",
    "google/gemini-3.5-flash",
    "ibm-granite/granite-4.1-8b",
    "meta-llama/llama-3.3-70b-instruct",
    "qwen/qwen3-32b",
    "mistralai/mistral-small-3.2-24b-instruct",
]
DEFAULT_OUT = REPO / "content/eval/answer-generation-model-comparison-20260713"


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


def safe_name(model: str) -> str:
    return model.replace("/", "__").replace(":", "_")


def post(payload: dict[str, Any], key: str, timeout: int) -> dict[str, Any]:
    request = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/qs-paper-generator",
            "X-Title": "QS Paper Generator Answer Model Cost Eval",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return {
            "error": {
                "http_status": exc.code,
                "body": exc.read().decode(errors="replace"),
            }
        }
    except Exception as exc:  # noqa: BLE001
        return {"error": {"type": type(exc).__name__, "message": str(exc)}}


def message_text(response: dict[str, Any]) -> str:
    content = response["choices"][0]["message"]["content"]
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            str(item.get("text") or "") for item in content if isinstance(item, dict)
        )
    return str(content or "")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ingestion-job", type=int, default=13)
    parser.add_argument("--models", default=",".join(DEFAULT_MODELS))
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--max-tokens", type=int, default=12000)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    load_env()
    import django

    django.setup()
    from langchain_core.output_parsers import PydanticOutputParser

    from bank.answer_generation import USABLE_PARSE_QUALITIES
    from bank.answer_generation_core import (
        AnswerQuestion,
        BatchAnswers,
        build_answer_prompt,
    )
    from bank.models import IngestionJob

    key = os.environ["OPENROUTER_API_KEY"]
    job = IngestionJob.objects.get(pk=args.ingestion_job)
    stored = list(
        job.questions.filter(parse_quality__in=USABLE_PARSE_QUALITIES)
        .select_related("chapter")
        .order_by("section", "id")
    )
    questions = [AnswerQuestion.from_model(question) for question in stored]
    output_parser = PydanticOutputParser(pydantic_object=BatchAnswers)
    prompt = build_answer_prompt(questions, output_parser.get_format_instructions())
    expected_ids = [question.id for question in questions]

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "prompt.txt").write_text(prompt)
    (args.out / "question-set.json").write_text(
        json.dumps(
            [
                {
                    "id": question.id,
                    "qtype": question.qtype,
                    "marks": question.marks,
                    "chapter": question.chapter,
                    "text": question.text,
                    "options": list(question.options),
                    "content": question.content,
                }
                for question in questions
            ],
            ensure_ascii=False,
            indent=2,
        )
    )
    config = {
        "ingestion_job_id": args.ingestion_job,
        "question_set_size": len(questions),
        "question_ids": expected_ids,
        "models": [item.strip() for item in args.models.split(",") if item.strip()],
        "temperature": 0,
        "max_tokens": args.max_tokens,
        "production_code": [
            "AnswerQuestion.from_model",
            "build_answer_prompt",
            "PydanticOutputParser(BatchAnswers)",
        ],
        "database_writes": False,
    }
    (args.out / "run-config.json").write_text(json.dumps(config, indent=2))

    rows: list[dict[str, Any]] = []
    for model in config["models"]:
        model_dir = args.out / safe_name(model)
        model_dir.mkdir(parents=True, exist_ok=True)
        summary_path = model_dir / "summary.json"
        if summary_path.is_file() and not args.force:
            row = json.loads(summary_path.read_text())
            rows.append(row)
            print(json.dumps({**row, "status": "reused"}), flush=True)
            continue

        payload: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "max_tokens": args.max_tokens,
            "usage": {"include": True},
        }
        # Answer text should be concise; hidden reasoning would add cost and makes
        # latency less comparable. Gemini 3.5 currently rejects disabled reasoning.
        if model != "google/gemini-3.5-flash":
            payload["reasoning"] = {"enabled": False}
        (model_dir / "request.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2)
        )

        started = time.monotonic()
        response = post(payload, key, args.timeout)
        latency_ms = int((time.monotonic() - started) * 1000)
        (model_dir / "response.json").write_text(
            json.dumps(response, ensure_ascii=False, indent=2)
        )
        usage = response.get("usage") or {}
        row: dict[str, Any] = {
            "model": model,
            "question_set_size": len(questions),
            "latency_ms": latency_ms,
            "input_tokens": usage.get("prompt_tokens"),
            "output_tokens": usage.get("completion_tokens"),
            "reasoning_tokens": (usage.get("completion_tokens_details") or {}).get(
                "reasoning_tokens"
            ),
            "cost_usd": usage.get("cost"),
            "provider": None,
            "finish_reason": None,
            "answers_returned": 0,
            "missing_ids": expected_ids,
            "duplicate_ids": [],
            "unexpected_ids": [],
            "blank_ids": [],
            "valid_output": False,
            "error": "",
        }
        try:
            choice = response["choices"][0]
            row["finish_reason"] = choice.get("finish_reason")
            row["provider"] = response.get("provider")
            parsed = output_parser.parse(message_text(response))
            seen: set[int] = set()
            accepted: list[dict[str, Any]] = []
            for item in parsed.answers:
                if item.id not in expected_ids:
                    if item.id not in row["unexpected_ids"]:
                        row["unexpected_ids"].append(item.id)
                    continue
                if item.id in seen:
                    if item.id not in row["duplicate_ids"]:
                        row["duplicate_ids"].append(item.id)
                    continue
                seen.add(item.id)
                answer = item.answer.strip()
                if not answer:
                    row["blank_ids"].append(item.id)
                    continue
                accepted.append({"id": item.id, "answer": answer})
            accepted_ids = {item["id"] for item in accepted}
            row["answers_returned"] = len(accepted)
            row["missing_ids"] = [item for item in expected_ids if item not in accepted_ids]
            row["valid_output"] = not (
                row["missing_ids"]
                or row["duplicate_ids"]
                or row["unexpected_ids"]
                or row["blank_ids"]
            )
            (model_dir / "answers.json").write_text(
                json.dumps(accepted, ensure_ascii=False, indent=2)
            )
        except Exception as exc:  # noqa: BLE001
            row["error"] = f"{type(exc).__name__}: {exc}"
            if response.get("error"):
                row["error"] = json.dumps(response["error"], ensure_ascii=False)[:2000]

        summary_path.write_text(json.dumps(row, ensure_ascii=False, indent=2))
        rows.append(row)
        (args.out / "results.json").write_text(
            json.dumps(rows, ensure_ascii=False, indent=2)
        )
        print(json.dumps(row, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
