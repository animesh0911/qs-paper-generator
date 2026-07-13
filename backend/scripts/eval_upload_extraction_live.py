#!/usr/bin/env python3
"""Run a live OCR + LLM upload-extraction cost eval.

Example:

    cd backend
    uv run python scripts/eval_upload_extraction_live.py \
      media/ingestion_uploads/2025_science_paper6.pdf \
      --provider openrouter \
      --models google/gemini-3.5-flash,qwen/qwen3.7-plus \
      --batch-sizes 1,5,all \
      --out-dir ../content/eval/upload-runs/run-001 \
      --yes

This script uses real API keys. It runs Mistral OCR once per PDF/run-dir and
reuses the cached OCR output for every LLM model and batch size.
"""

from __future__ import annotations

import argparse
import os
import shlex
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
            try:
                parts = shlex.split(raw_line, comments=True, posix=True)
            except ValueError:
                continue
            if len(parts) != 1 or "=" not in parts[0]:
                continue
            key, value = parts[0].split("=", 1)
            if key.strip() and not os.environ.get(key.strip()):
                os.environ[key.strip()] = value


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _batch_sizes(value: str):
    out = []
    for item in _csv(value):
        if item.lower() == "all":
            out.append("all")
        else:
            out.append(int(item))
    return out


def main() -> int:
    _load_dotenv()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--provider", default="openrouter")
    parser.add_argument("--models", type=_csv, required=True)
    parser.add_argument("--batch-sizes", type=_batch_sizes, default=["all"])
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=REPO_DIR / "content/eval/upload-runs/latest",
    )
    parser.add_argument(
        "--ocr-model",
        default=os.getenv("MISTRAL_OCR_MODEL") or "mistral-ocr-latest",
    )
    parser.add_argument(
        "--ocr-usd-per-1000-pages",
        type=float,
        default=4.0,
        help="Used for per-run cost reporting; default $4/1000 pages (OCR 4 standard API).",
    )
    parser.add_argument(
        "--filter-policy",
        choices=["english-question", "none"],
        default="english-question",
    )
    parser.add_argument("--no-reuse-ocr", action="store_true")
    parser.add_argument(
        "--max-batches",
        type=int,
        default=0,
        help="Debug spend guard: 0 = all batches for every model.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Consent to live Mistral OCR and LLM API calls.",
    )
    args = parser.parse_args()

    if not args.pdf.is_file():
        raise SystemExit(f"PDF not found: {args.pdf}")

    planned = len(args.models) * len(args.batch_sizes)
    print("Live upload extraction eval")
    print(f"  pdf: {args.pdf}")
    print(f"  OCR: {args.ocr_model} (reused={not args.no_reuse_ocr})")
    print(f"  provider: {args.provider}")
    print(f"  models: {', '.join(args.models)}")
    print(f"  batch_sizes: {', '.join(map(str, args.batch_sizes))}")
    print(f"  LLM cells: {planned}")
    print(f"  out_dir: {args.out_dir}")

    if not args.yes:
        print("\nDRY RUN: pass --yes to call OCR/LLM APIs.")
        return 0

    import django

    django.setup()

    from bank.upload_extraction import run_live_upload_extraction_eval

    rows = run_live_upload_extraction_eval(
        pdf_path=args.pdf,
        provider=args.provider,
        models=args.models,
        batch_sizes=args.batch_sizes,
        out_dir=args.out_dir,
        ocr_model=args.ocr_model,
        ocr_usd_per_1000_pages=args.ocr_usd_per_1000_pages,
        reuse_ocr=not args.no_reuse_ocr,
        filter_policy=args.filter_policy,
        max_batches=args.max_batches,
    )

    print("\nResults")
    print("pdf_pages,ocr_billable_pages,ocr_model,ocr_cost,ocr_latency,ocr_output_size,"
          "llm_model,batch_size,llm_cost,llm_latency,total_cost,questions")
    for row in rows:
        values = row.simple_csv_dict()
        print(
            ",".join(
                "" if values[key] is None else str(values[key])
                for key in (
                    "pdf_pages",
                    "ocr_billable_pages",
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
                )
            )
        )
    print(f"\nwrote {args.out_dir / 'results.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
