#!/usr/bin/env python3
"""Run Mistral OCR for one NCERT textbook PDF and save corpus artifacts.

This script only creates developer-reviewed artifacts; database import stays in
``import_mistral_ocr_textbook_document`` / ``seed_textbook_corpus``.
"""

from __future__ import annotations

import argparse
import json
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
            key = key.strip()
            if key and not os.environ.get(key):
                os.environ[key] = value


def main() -> int:
    _load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--basename", default="jesc110")
    parser.add_argument("--reuse-ocr", action="store_true")
    args = parser.parse_args()

    if not args.pdf.is_file():
        raise SystemExit(f"PDF not found: {args.pdf}")

    import django

    django.setup()

    from bank.ocr_extractor import MistralOcrClient
    from corpus.textbook import pages_from_mistral_ocr

    args.out_dir.mkdir(parents=True, exist_ok=True)
    ocr_path = args.out_dir / f"{args.basename}_ocr.json"
    canonical_path = args.out_dir / f"{args.basename}.json"
    markdown_path = args.out_dir / f"{args.basename}.md"

    if args.reuse_ocr:
        if not ocr_path.is_file():
            raise SystemExit(f"--reuse-ocr requested but not found: {ocr_path}")
        ocr = json.loads(ocr_path.read_text(encoding="utf-8"))
        print(f"Reuse OCR artifact: {ocr_path}")
    else:
        print(f"OCR whole PDF: {args.pdf}")
        ocr = MistralOcrClient().process_pdf(args.pdf.read_bytes())
        ocr_path.write_text(
            json.dumps(ocr, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    pages = pages_from_mistral_ocr(ocr)
    markdown_path.write_text(
        "\n\n".join(
            f"--- PAGE {page['page_number']} ---\n\n{page['markdown']}"
            for page in pages
        ),
        encoding="utf-8",
    )
    canonical_path.write_text(
        json.dumps(ocr, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"pages={len(pages)}")
    print(f"ocr={ocr_path}")
    print(f"canonical={canonical_path}")
    print(f"markdown={markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
