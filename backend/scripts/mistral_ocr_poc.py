#!/usr/bin/env python3
"""POC: Mistral OCR -> structured bank questions -> optional source persistence.

This is intentionally a standalone harness, not the production drainer. It lets
us validate the risky part of the proposed flow with one sample PDF:

    PDF -> Mistral OCR API -> page markdown -> Mistral chat JSON structuring
        -> Ingestor.ingest_extracted(..., ingestion_job=job)
        -> /api/bank/sources/ shows upload:<job_id>

Env:
    MISTRAL_API_KEY                 required
    MISTRAL_OCR_MODEL               default: mistral-ocr-latest
    MISTRAL_STRUCTURE_MODEL         default: mistral-large-latest
    MISTRAL_BASE_URL                default: https://api.mistral.ai/v1

Examples:
    # OCR + structure only, write artifacts, do not touch DB
    DJANGO_DEBUG=1 MISTRAL_API_KEY=... python scripts/mistral_ocr_poc.py sample.pdf

    # Persist into the teacher account so source selection can display upload:<id>
    DJANGO_DEBUG=1 MISTRAL_API_KEY=... python scripts/mistral_ocr_poc.py sample.pdf \
      --persist --teacher-email teacher@example.com --source-type previous_year_paper
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

# Make the script runnable as `python scripts/mistral_ocr_poc.py` from backend/.
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402


def _post_json(url: str, api_key: str, payload: dict[str, Any], timeout: int) -> dict:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{url} returned HTTP {exc.code}: {detail}") from exc


def _ocr_pdf(pdf_path: Path, *, api_key: str, base_url: str, model: str) -> dict:
    encoded = base64.b64encode(pdf_path.read_bytes()).decode("ascii")
    payload = {
        "model": model,
        "document": {
            "type": "document_url",
            "document_url": f"data:application/pdf;base64,{encoded}",
        },
        "include_image_base64": False,
    }
    return _post_json(f"{base_url}/ocr", api_key, payload, timeout=300)


def _pages_from_ocr(ocr: dict) -> list[dict[str, Any]]:
    pages = ocr.get("pages")
    if not isinstance(pages, list):
        return [{"index": 0, "markdown": json.dumps(ocr, ensure_ascii=False)}]
    out: list[dict[str, Any]] = []
    for i, page in enumerate(pages):
        if not isinstance(page, dict):
            continue
        markdown = page.get("markdown") or page.get("text") or ""
        out.append({"index": page.get("index", i), "markdown": markdown})
    return out


def _structure_page(
    markdown: str,
    *,
    api_key: str,
    base_url: str,
    model: str,
    schema: dict,
) -> dict:
    prompt = f"""
You are converting OCR markdown from ONE PAGE of a CBSE Class 10 Science question paper into JSON.
Extract only English questions visible on this page. Ignore instructions, headers, footers, page numbers, and Hindi text.
Return JSON only, with this top-level shape: {{"questions": [...]}}.

Each question object must follow this schema intent:
- section: A/B/C/D/E if visible, otherwise best guess
- qtype: one of mcq, assertion_reason, very_short_answer, short_answer, long_answer, case_based
- marks: integer marks printed for the question
- rawText: verbatim question stem, no option labels and no marks
- options: MCQ/assertion options as [{{"label":"A","text":"..."}}], else []
- content: at minimum {{"stem":[{{"type":"paragraph","text":"..."}}]}}
- chapter_slug: one of the allowed chapter slugs if clear, otherwise null
- cognitive_level: one of R, U, Ap, An
- topic_names: [] if unclear
- primary_form: none, diagram_based, or table_based
- figures: [] for this POC unless OCR explicitly gives a figure reference

Allowed JSON schema, for reference:
{json.dumps(schema, ensure_ascii=False)}

OCR markdown:
```markdown
{markdown}
```
""".strip()
    payload = {
        "model": model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": "Return strict JSON only. Do not wrap in markdown.",
            },
            {"role": "user", "content": prompt},
        ],
    }
    response = _post_json(f"{base_url}/chat/completions", api_key, payload, timeout=300)
    content = response["choices"][0]["message"]["content"]
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Structuring model returned non-JSON: {content[:500]}") from exc
    if not isinstance(parsed, dict):
        return {"questions": []}
    parsed.setdefault("questions", [])
    return parsed


def _persist(
    *,
    pdf_path: Path,
    questions: list[dict],
    teacher_email: str,
    source_type: str,
) -> None:
    from accounts.models import User
    from bank.ingestor import Ingestor
    from bank.models import IngestionJob, IngestionJobStatus
    from django.core.files.base import ContentFile

    user = User.objects.get(email=teacher_email)
    job = IngestionJob.objects.create(
        school=user.school,
        created_by=user,
        source_file_name=pdf_path.name,
        source_type=source_type,
        status=IngestionJobStatus.RUNNING,
    )
    job.pdf.save(pdf_path.name, ContentFile(pdf_path.read_bytes()), save=True)

    try:
        result = Ingestor().ingest_extracted(
            questions,
            source_file_name=pdf_path.name,
            source_type=source_type,
            school=user.school,
            pdf_bytes=None,
            ingestion_job=job,
        )
    except Exception as exc:  # noqa: BLE001 - POC records failure on the source job.
        job.status = IngestionJobStatus.FAILED
        job.error = f"{type(exc).__name__}: {exc}"
        job.save(update_fields=["status", "error", "updated_at"])
        raise

    job.status = IngestionJobStatus.DONE
    job.created_count = result.created
    job.skipped_count = result.skipped_duplicates
    job.error = ""
    job.pages_done = job.total_pages = 0
    job.save(
        update_fields=[
            "status",
            "created_count",
            "skipped_count",
            "error",
            "pages_done",
            "total_pages",
            "updated_at",
        ]
    )
    print(
        f"persisted ingestion_job={job.pk} key=upload:{job.pk} "
        f"created={result.created} skipped={result.skipped_duplicates}"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--out-dir", type=Path, default=Path("/tmp/mistral-ocr-poc"))
    parser.add_argument("--persist", action="store_true")
    parser.add_argument("--teacher-email", default="teacher@example.com")
    parser.add_argument("--source-type", default="previous_year_paper")
    parser.add_argument("--max-pages", type=int, default=0, help="0 = all pages")
    args = parser.parse_args()

    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        raise SystemExit("MISTRAL_API_KEY is required")
    base_url = os.getenv("MISTRAL_BASE_URL", "https://api.mistral.ai/v1").rstrip("/")
    ocr_model = os.getenv("MISTRAL_OCR_MODEL", "mistral-ocr-latest")
    structure_model = os.getenv("MISTRAL_STRUCTURE_MODEL", "mistral-large-latest")

    if not args.pdf.is_file():
        raise SystemExit(f"PDF not found: {args.pdf}")

    django.setup()
    from bank.extraction import build_question_schema, merge_page_payloads
    from bank.models import Chapter

    args.out_dir.mkdir(parents=True, exist_ok=True)
    print(f"OCR {args.pdf} with {ocr_model}...")
    ocr = _ocr_pdf(args.pdf, api_key=api_key, base_url=base_url, model=ocr_model)
    (args.out_dir / "ocr.json").write_text(json.dumps(ocr, indent=2, ensure_ascii=False))

    pages = _pages_from_ocr(ocr)
    if args.max_pages > 0:
        pages = pages[: args.max_pages]
    (args.out_dir / "ocr.md").write_text(
        "\n\n--- PAGE ---\n\n".join(page["markdown"] for page in pages),
        encoding="utf-8",
    )
    print(f"OCR pages={len(pages)}; structuring with {structure_model}...")

    schema = build_question_schema(Chapter.objects.values_list("slug", flat=True))
    payloads = []
    for page in pages:
        markdown = page["markdown"] or ""
        if not markdown.strip():
            payloads.append({"questions": []})
            continue
        payload = _structure_page(
            markdown,
            api_key=api_key,
            base_url=base_url,
            model=structure_model,
            schema=schema,
        )
        payloads.append(payload)
        print(f"page {page['index']}: {len(payload.get('questions', []))} raw question(s)")

    (args.out_dir / "structured_page_payloads.json").write_text(
        json.dumps(payloads, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    questions = merge_page_payloads(payloads)
    (args.out_dir / "questions.json").write_text(
        json.dumps(questions, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"coerced unique questions={len(questions)}")
    print(f"artifacts={args.out_dir}")

    if args.persist:
        if not questions:
            raise SystemExit("No questions to persist")
        _persist(
            pdf_path=args.pdf,
            questions=questions,
            teacher_email=args.teacher_email,
            source_type=args.source_type,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
