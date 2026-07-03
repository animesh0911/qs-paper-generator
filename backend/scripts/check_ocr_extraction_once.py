#!/usr/bin/env python3
"""Run the existing extraction path once with an OCR step in front.

This is not a separate ingestion pipeline. It uses the existing schema, payload
merger, and optional ``Ingestor.ingest_extracted`` tail. The only experimental
piece is the extractor adapter:

    page PDF -> Mistral OCR markdown -> configured extraction LLM -> questions

Configure the cheap structuring model through the existing model seam, for
example in .env or inline:

    LLM_EXTRACTION_PROVIDER=deepseek
    LLM_EXTRACTION_MODEL=deepseek-chat
    DEEPSEEK_API_KEY=...

or GLM/OpenAI-compatible via the OpenAI provider/base URL:

    LLM_EXTRACTION_PROVIDER=openai
    LLM_EXTRACTION_MODEL=glm-4-flash
    OPENAI_API_KEY=...
    OPENAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4

Examples:

    cd backend
    python3 scripts/check_ocr_extraction_once.py sample.pdf --max-pages 2

    python3 scripts/check_ocr_extraction_once.py sample.pdf \
      --persist --teacher-email teacher@example.com
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

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
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def _persist(
    *, pdf_path: Path, questions: list[dict], teacher_email: str, source_type: str
):
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
            # Questions-only check: skip diagram cropping for now.
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

    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument(
        "--out-dir", type=Path, default=Path("/tmp/ocr-extraction-check")
    )
    parser.add_argument("--max-pages", type=int, default=0, help="0 = all pages")
    parser.add_argument("--persist", action="store_true")
    parser.add_argument("--teacher-email", default="teacher@example.com")
    parser.add_argument("--source-type", default="previous_year_paper")
    args = parser.parse_args()

    if not args.pdf.is_file():
        raise SystemExit(f"PDF not found: {args.pdf}")

    import django

    django.setup()

    from bank.extraction import merge_page_payloads, split_pages
    from bank.ocr_extractor import MistralOcrMarkdownExtractor

    args.out_dir.mkdir(parents=True, exist_ok=True)
    extractor = MistralOcrMarkdownExtractor()

    pdf_bytes = args.pdf.read_bytes()
    pages = split_pages(pdf_bytes)
    if args.max_pages > 0:
        pages = pages[: args.max_pages]

    payloads = []
    markdowns = []
    print(f"OCR+extract {len(pages)} page(s) from {args.pdf}...")
    for index, page_bytes in enumerate(pages):
        markdown = extractor.ocr_client.markdown_for_pdf(page_bytes)
        markdowns.append(markdown)
        payload = (
            extractor.structure_markdown(markdown) if markdown else {"questions": []}
        )
        payloads.append(payload)
        print(f"page {index}: {len(payload.get('questions', []))} raw question(s)")

    questions = merge_page_payloads(payloads)

    (args.out_dir / "ocr.md").write_text(
        "\n\n--- PAGE ---\n\n".join(markdowns), encoding="utf-8"
    )
    (args.out_dir / "structured_page_payloads.json").write_text(
        json.dumps(payloads, indent=2, ensure_ascii=False), encoding="utf-8"
    )
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
