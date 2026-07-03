#!/usr/bin/env python3
"""Whole-PDF Mistral OCR + batched LLM question structuring POC.

This is the cheaper experiment shape for bilingual CBSE papers:

    whole PDF -> Mistral OCR once -> filter English/question pages
        -> batch N OCR pages per OpenRouter/LLM call -> merge questions

It writes artifacts by default and only persists when --persist is provided.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import sys
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")


def _load_dotenv() -> None:
    for path in (REPO_DIR / ".env", BACKEND_DIR / ".env"):
        if not path.is_file():
            continue
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            try:
                parts = shlex.split(raw_line, comments=True, posix=True)
            except ValueError:
                continue
            if len(parts) != 1 or "=" not in parts[0]:
                continue
            key, value = parts[0].split("=", 1)
            key = key.strip()
            if key and not os.environ.get(key):
                os.environ[key] = value


def _copy_generation_llm_to_extraction_defaults() -> None:
    """Use the existing OpenRouter question-generation key/model for parsing.

    The app's model seam looks at LLM_EXTRACTION_* for this task. Local envs in
    this repo often only set LLM_QUESTION_GENERATION_*; for this POC, copy them
    unless the caller explicitly chose an extraction model.
    """
    if "LLM_EXTRACTION_PROVIDER" not in os.environ:
        provider = os.getenv("LLM_QUESTION_GENERATION_PROVIDER")
        if provider:
            os.environ["LLM_EXTRACTION_PROVIDER"] = provider
    if "LLM_EXTRACTION_MODEL" not in os.environ:
        model = os.getenv("LLM_QUESTION_GENERATION_MODEL")
        if model:
            os.environ["LLM_EXTRACTION_MODEL"] = model


def _pages_from_ocr(ocr: dict[str, Any]) -> list[dict[str, Any]]:
    pages = ocr.get("pages")
    if not isinstance(pages, list):
        return [{"index": 0, "markdown": json.dumps(ocr, ensure_ascii=False)}]
    out: list[dict[str, Any]] = []
    for i, page in enumerate(pages):
        if not isinstance(page, dict):
            continue
        markdown = page.get("markdown") or page.get("text") or ""
        out.append({"index": int(page.get("index", i)), "markdown": str(markdown)})
    return out


def _looks_hindi_only(markdown: str) -> bool:
    devanagari = len(re.findall(r"[\u0900-\u097F]", markdown))
    latin = len(re.findall(r"[A-Za-z]", markdown))
    if devanagari < 40:
        return False
    return latin < max(40, devanagari // 6)


def _looks_questionish(markdown: str) -> bool:
    if not markdown.strip():
        return False
    latin = len(re.findall(r"[A-Za-z]", markdown))
    if latin >= 80:
        return True
    patterns = (
        r"(^|\n)\s*(?:Q\.?\s*)?\d{1,2}\s*[.)]",
        r"Questions?\s+no",
        r"SECTION\s+[A-E]",
        r"Assertion\s*\(A\)",
        r"\*\*OR\*\*|\bOR\b",
    )
    return any(re.search(pattern, markdown, re.IGNORECASE) for pattern in patterns)


def _filter_pages(pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected = []
    for page in pages:
        markdown = page["markdown"]
        if _looks_hindi_only(markdown):
            continue
        if not _looks_questionish(markdown):
            continue
        selected.append(page)
    return selected


def _batch_pages(
    pages: list[dict[str, Any]], batch_pages: int
) -> list[list[dict[str, Any]]]:
    return [pages[i : i + batch_pages] for i in range(0, len(pages), batch_pages)]


def _batch_markdown(batch: list[dict[str, Any]]) -> str:
    parts = []
    for page in batch:
        page_no = int(page["index"]) + 1
        parts.append(f"\n\n===== OCR PAGE {page_no} =====\n\n{page['markdown']}")
    return "".join(parts).strip()


def _persist(
    *, pdf_path: Path, questions: list[dict], teacher_email: str, source_type: str
) -> None:
    from django.core.files.base import ContentFile

    from accounts.models import User
    from bank.ingestor import Ingestor
    from bank.models import IngestionJob, IngestionJobStatus

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
    except Exception as exc:  # noqa: BLE001
        job.status = IngestionJobStatus.FAILED
        job.error = f"{type(exc).__name__}: {exc}"
        job.save(update_fields=["status", "error", "updated_at"])
        raise

    job.status = IngestionJobStatus.DONE
    job.created_count = result.created
    job.skipped_count = result.skipped_duplicates
    job.error = ""
    job.save(
        update_fields=[
            "status",
            "created_count",
            "skipped_count",
            "error",
            "updated_at",
        ]
    )
    print(
        f"persisted ingestion_job={job.pk} key=upload:{job.pk} "
        f"created={result.created} skipped={result.skipped_duplicates}"
    )


def main() -> int:
    _load_dotenv()
    _copy_generation_llm_to_extraction_defaults()

    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument(
        "--out-dir", type=Path, default=Path("/tmp/mistral-ocr-batch-poc")
    )
    parser.add_argument(
        "--batch-pages",
        type=int,
        default=999,
        help="OCR markdown pages per LLM structuring call; default is one-shot.",
    )
    parser.add_argument("--max-batches", type=int, default=0, help="0 = all batches")
    parser.add_argument(
        "--reuse-ocr",
        action="store_true",
        help="Read existing out-dir/ocr.json instead of calling Mistral OCR again.",
    )
    parser.add_argument("--persist", action="store_true")
    parser.add_argument("--teacher-email", default="teacher@example.com")
    parser.add_argument("--source-type", default="previous_year_paper")
    args = parser.parse_args()

    if args.batch_pages < 1:
        raise SystemExit("--batch-pages must be >= 1")
    if not args.pdf.is_file():
        raise SystemExit(f"PDF not found: {args.pdf}")

    import django

    django.setup()

    from bank.extraction import merge_page_payloads
    from bank.ocr_extractor import MistralOcrClient, MistralOcrMarkdownExtractor

    args.out_dir.mkdir(parents=True, exist_ok=True)
    pdf_bytes = args.pdf.read_bytes()

    ocr_client = MistralOcrClient()
    ocr_path = args.out_dir / "ocr.json"
    if args.reuse_ocr:
        if not ocr_path.is_file():
            raise SystemExit(f"--reuse-ocr requested but not found: {ocr_path}")
        print(f"Reuse OCR artifact: {ocr_path}")
        ocr = json.loads(ocr_path.read_text(encoding="utf-8"))
    else:
        print(f"OCR whole PDF once: {args.pdf}")
        ocr = ocr_client.process_pdf(pdf_bytes)
        ocr_path.write_text(
            json.dumps(ocr, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    pages = _pages_from_ocr(ocr)
    selected = _filter_pages(pages)
    batches = _batch_pages(selected, args.batch_pages)
    if args.max_batches > 0:
        batches = batches[: args.max_batches]

    (args.out_dir / "ocr_all.md").write_text(
        "\n\n--- PAGE ---\n\n".join(page["markdown"] for page in pages),
        encoding="utf-8",
    )
    (args.out_dir / "selected_pages.json").write_text(
        json.dumps(
            [
                {"page": page["index"] + 1, "chars": len(page["markdown"])}
                for page in selected
            ],
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        f"OCR pages={len(pages)}; selected English/question pages={len(selected)}; "
        f"LLM batches={len(batches)} x up to {args.batch_pages} pages"
    )

    extractor = MistralOcrMarkdownExtractor(ocr_client=ocr_client)
    payloads = []
    batch_artifacts = []
    for batch_index, batch in enumerate(batches, start=1):
        page_numbers = [page["index"] + 1 for page in batch]
        markdown = _batch_markdown(batch)
        payload = extractor.structure_markdown(markdown)
        payloads.append(payload)
        batch_artifacts.append(
            {"batch": batch_index, "pages": page_numbers, "payload": payload}
        )
        print(
            f"batch {batch_index}/{len(batches)} pages={page_numbers}: "
            f"{len(payload.get('questions', []))} raw question(s)"
        )

    (args.out_dir / "structured_batches.json").write_text(
        json.dumps(batch_artifacts, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    questions = merge_page_payloads(payloads)
    (args.out_dir / "questions.json").write_text(
        json.dumps(questions, indent=2, ensure_ascii=False), encoding="utf-8"
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
