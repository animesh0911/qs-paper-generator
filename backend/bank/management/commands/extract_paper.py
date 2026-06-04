"""extract_paper — extract one source PDF into committed JSON (+ cropped diagrams).

The offline, key-requiring producer for the committed-JSON path. It sends one
paper PDF to ``GeminiExtractor`` (needs ``GEMINI_API_KEY``), crops any localised
figures into ``<out>/assets/`` (no extra LLM call — pure PyMuPDF), and dumps the
extracted, tagged question dicts as a single ``content/parsed/*.json`` file in
the exact shape ``load_questions`` consumes.

The LLM step runs once, offline; its reviewed output (JSON + assets) is
committed. Replaying that committed JSON with ``load_questions`` is then
deterministic and needs no key — that replay is the "no-API-key" path, not this
command.

It does NOT touch the database and does NOT generate answers.
The intended pipeline is::

    python manage.py extract_paper /content/science_2026/31_1_1_Science.pdf
    # review content/parsed/31_1_1_Science.json by hand
    python manage.py load_questions /content/parsed/
    python manage.py generate_answers

``--out`` overrides the output directory (default ``/content/parsed/``).
"""

from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from bank.content import has_item
from bank.diagram_cropper import crop_to_dir
from bank.ingestor import GeminiExtractor, _fingerprint


class Command(BaseCommand):
    help = "Extract one source PDF into a committed content/parsed/ JSON file."

    def add_arguments(self, parser):
        parser.add_argument(
            "pdf",
            type=str,
            help="Path to the source PDF, e.g. /content/science_2026/31_1_1.pdf.",
        )
        parser.add_argument(
            "--out",
            type=str,
            default="/content/parsed",
            help="Output directory for the JSON file (default: /content/parsed).",
        )

    def handle(self, *args, **options):
        pdf_path = Path(options["pdf"])
        if not pdf_path.is_file():
            raise CommandError(f"Not a file: {pdf_path}")

        out_dir = Path(options["out"])
        out_dir.mkdir(parents=True, exist_ok=True)

        # source_pdf is recorded relative to content/ (parent dir + filename) so
        # load_questions' _parse_source_filename can derive the year from the
        # parent (e.g. science_2026 → 2026).
        source_pdf = f"{pdf_path.parent.name}/{pdf_path.name}"

        pdf_bytes = pdf_path.read_bytes()
        self.stdout.write(
            f"Extracting {source_pdf} (this calls the LLM, may take minutes)..."
        )
        questions = GeminiExtractor().extract(pdf_bytes)
        if not questions:
            raise CommandError(f"Extractor returned no questions for {source_pdf}.")

        # Crop figures to committed PNGs (no LLM): rewrites each question's
        # image_placeholder into an image item referencing the saved asset, so
        # load_questions re-hydrates real diagrams. Assets live beside the JSON.
        fingerprints = [_fingerprint(q["text"]) for q in questions]
        crop_to_dir(pdf_bytes, questions, fingerprints, out_dir / "assets")
        cropped = sum(1 for q in questions if has_item(q.get("content", {}), "image"))

        out_path = out_dir / f"{pdf_path.stem}.json"
        out_path.write_text(
            json.dumps({"source_pdf": source_pdf, "questions": questions}, indent=2)
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Wrote {len(questions)} question(s) ({cropped} with cropped "
                f"diagram) to {out_path}."
            )
        )
