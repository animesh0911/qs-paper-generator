#!/usr/bin/env python3
"""Compare OpenRouter structuring models against cached GLM-OCR Markdown."""
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

MODELS = [
    "deepseek/deepseek-v4-flash",
    "mistralai/mistral-small-3.2-24b-instruct",
    "nvidia/nemotron-3-super-120b-a12b",
    "xiaomi/mimo-v2.5",
    "deepseek/deepseek-v4-pro",
    "z-ai/glm-5.2",
    "nvidia/nemotron-3-ultra-550b-a55b",
    "google/gemini-3.5-flash",
    "moonshotai/kimi-k2.6",
]
OCR_COST = 0.00280884
OCR_MD = REPO / "content/eval/upload-runs/31-5-2-science-glm-ocr/ocr.md"
OUT = REPO / "content/eval/upload-runs/31-5-2-science-glm-ocr-llm-matrix"


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


def prompt(markdown: str, schema: dict[str, Any]) -> str:
    return f"""You are converting GLM-OCR Markdown from a standard bilingual CBSE Class 10 Science examination paper into independent question-bank entries.

The source contains printed Question Nos. 1-39 in Hindi and English. Extract only English. The output may contain more than 39 entries because every internal OR alternative must become an independently usable bank entry.

Rules:
- Completely ignore Hindi/Devanagari content. Never translate it or merge it into English.
- Extract every printed English question in source order. Copy wording verbatim; never answer, paraphrase, correct, complete, or invent content.
- Ignore cover text, general instructions after applying their rules, section descriptions, headers, footers, page numbers, Q.P. codes, roll-number fields, watermarks, and shared assertion-reason answer-code instructions.
- Ordinary (a)/(b)/(c)/(i)/(ii) subparts stay together in content.subparts.
- For every internal OR choice, emit EACH alternative as a separate independently usable entry with its normal qtype. Duplicate necessary shared context. Do not emit internal_choice and do not keep both alternatives in one rawText.
- Case/source passages stay in content.passage with dependent questions in content.subparts. If an internal OR occurs, repeat necessary passage/common context in each independent entry.
- Do not include printed question numbers or printed mark digits in rawText.

Standard source structure:
- Printed 1-20: Section A, 1 mark. Ordinary objective questions are mcq; assertion/reason questions are assertion_reason.
- Printed 21-26: Section B, 2 marks, very_short_answer.
- Printed 27-33: Section C, 3 marks, short_answer.
- Printed 34-36: Section D, 5 marks, long_answer.
- Printed 37-39: Section E, 4 marks, case_based.
Accurate marks are essential; ingestion derives final section from marks.

Options/content:
- mcq/assertion_reason flat options: [{{"label":"A","text":"..."}}]. Otherwise options is [].
- Also populate content.options as [{{"label":"A","content":[{{"type":"paragraph","text":"..."}}]}}].
- Use content.stem for the stem, assertion/reason for assertion_reason, passage/subparts for case_based.
- rawText is the stem plus ordinary subparts, but excludes MCQ/assertion-reason options because they are stored separately.
- Preserve the semantic content of equations/LaTeX and HTML/Markdown tables. Formula fidelity is critical: retain chemical subscripts, superscripts, fractions, reaction arrows, charges, coefficients, units, mathematical symbols, and every numeric value.
- Render formulas as clean canonical LaTeX. Normalize obvious OCR spacing artifacts inside a single formula token. Required examples: `4 4 \\times1 0^{-6}` → `44 \\times 10^{-6}`, `N H_{3}` → `NH_{3}`, `P b` → `Pb`, and `N O_{2}` → `NO_{2}`. Apply the normalized form consistently in both rawText and structured content.
- Before returning JSON, inspect every formula for separated digits, separated element-symbol letters, and broken scientific notation; fix those spacing defects. Never change a coefficient, exponent, value, sign, unit, or chemical symbol. If normalization would require inventing a missing decimal point or other symbol, preserve the source instead of guessing.
- Keep readable formula text in rawText and canonical LaTeX in structured content; never flatten formula notation.

Visuals are out of scope:
- Never interpret diagrams, figures, images, circuits, graphs, structures, apparatus, or visual tables.
- GLM placeholders look like ![](page=N,bbox=[x0,y0,x1,y1]). Never infer their contents.
- If an entry cannot be answered without a visual, set primary_form to diagram_based or table_based. It will be deterministically removed before ingestion.
- Set figures to [] for every entry. Preserve only explicitly visible OCR text.

Taxonomy/output:
- Pick chapter_slug only from the supplied enum, else null. Use only allowed cognitive_level and primary_form values.
- Return strict JSON only matching the supplied schema. No markdown fences or extra fields.
- Verify all printed English questions are represented, OR alternatives are separate, no Hindi is included, and JSON matches the schema.

PRODUCTION OUTPUT SCHEMA:
{json.dumps(schema, ensure_ascii=False, separators=(',', ':'))}

GLM OCR MARKDOWN:
<glm_ocr_markdown>
{markdown}
</glm_ocr_markdown>"""


def post(payload: dict[str, Any], key: str) -> dict[str, Any]:
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/qs-paper-generator",
            "X-Title": "QS Paper Generator GLM Markdown Cost Eval",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=900) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        return {"error": {"http_status": exc.code, "body": body}}
    except Exception as exc:  # noqa: BLE001
        return {"error": {"type": type(exc).__name__, "message": str(exc)}}


def safe_name(model: str) -> str:
    return model.replace("/", "__").replace(":", "_")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ocr-md", type=Path, default=OCR_MD)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--models", default=",".join(MODELS))
    parser.add_argument("--ocr-cost", type=float, default=OCR_COST)
    args = parser.parse_args()
    models = [item.strip() for item in args.models.split(",") if item.strip()]
    load_env()
    import django
    django.setup()
    from bank.extraction import build_question_schema, genai_to_json_schema, merge_page_payloads
    from bank.ocr_extractor import _POC_CHAPTER_SLUGS, _drop_visual_questions
    from bank.question_shape import compute_parse_quality

    api_key = os.environ["OPENROUTER_API_KEY"]
    markdown = args.ocr_md.read_text()
    schema = build_question_schema(_POC_CHAPTER_SLUGS)
    json_schema = genai_to_json_schema(schema)
    text = prompt(markdown, schema)
    args.out.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []

    for model in models:
        existing_summary = args.out / safe_name(model) / "summary.json"
        if existing_summary.is_file():
            row = json.loads(existing_summary.read_text())
            if row.get("valid_json"):
                rows.append(row)
                print(json.dumps({**row, "status": "reused"}), flush=True)
                continue
        started = time.monotonic()
        request_payload = {
            "model": model,
            "messages": [{"role": "user", "content": text}],
            "temperature": 0,
            "max_tokens": 30000,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "cbse_questions", "strict": True, "schema": json_schema},
            },
        }
        # Most extraction models should not spend tokens reasoning. Gemini 3.5
        # Flash currently requires reasoning at its OpenRouter endpoint.
        if model != "google/gemini-3.5-flash":
            request_payload["reasoning"] = {"enabled": False}
        response = post(request_payload, api_key)
        latency = int((time.monotonic() - started) * 1000)
        model_dir = args.out / safe_name(model)
        model_dir.mkdir(parents=True, exist_ok=True)
        (model_dir / "response.json").write_text(json.dumps(response, ensure_ascii=False, indent=2))
        usage = response.get("usage") or {}
        row: dict[str, Any] = {
            "model": model,
            "latency_ms": latency,
            "input_tokens": usage.get("prompt_tokens"),
            "output_tokens": usage.get("completion_tokens"),
            "llm_cost_usd": usage.get("cost"),
            "ocr_cost_usd": args.ocr_cost,
            "total_cost_usd": (usage.get("cost") + args.ocr_cost) if isinstance(usage.get("cost"), (int, float)) else None,
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
            payload = json.loads(content) if isinstance(content, str) else content
            row["valid_json"] = True
            raw_count = len(payload.get("questions") or [])
            filtered = _drop_visual_questions(payload)
            filtered_count = len(filtered.get("questions") or [])
            questions = merge_page_payloads([filtered])
            qualities = [compute_parse_quality(q, q["qtype"]) for q in questions]
            row.update({
                "raw_entries": raw_count,
                "visual_removed": raw_count - filtered_count,
                "persistable_entries": len(questions),
                "clean": qualities.count("clean"),
                "partial": qualities.count("partial"),
                "broken": qualities.count("broken"),
            })
            (model_dir / "payload.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2))
            (model_dir / "questions.json").write_text(json.dumps(questions, ensure_ascii=False, indent=2))
        except Exception as exc:  # noqa: BLE001
            row["error"] = f"{type(exc).__name__}: {exc}"
            if response.get("error"):
                row["error"] = json.dumps(response["error"], ensure_ascii=False)[:1000]
        (model_dir / "summary.json").write_text(json.dumps(row, indent=2))
        rows.append(row)
        (args.out / "results.json").write_text(json.dumps(rows, indent=2))
        print(json.dumps(row), flush=True)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
