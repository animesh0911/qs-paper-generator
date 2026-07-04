"""Import one existing Mistral OCR JSON artifact into the textbook corpus."""

from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from bank.models import Chapter
from corpus.importer import CorpusImporter, CorpusImportRequest


class Command(BaseCommand):
    help = "Import an existing Mistral OCR JSON file into TextbookElements."

    def add_arguments(self, parser):
        parser.add_argument("json_path", type=Path)
        parser.add_argument("--chapter", required=True, help="Canonical Chapter slug.")
        parser.add_argument("--source-file-name", required=True)
        parser.add_argument("--source-hash", required=True)
        parser.add_argument("--extractor-version", default="mistral-ocr-latest")

    def handle(self, *args, **options):
        path: Path = options["json_path"]
        if not path.is_file():
            raise CommandError(f"Mistral OCR JSON not found: {path}")
        try:
            chapter = Chapter.objects.get(slug=options["chapter"])
        except Chapter.DoesNotExist as exc:
            raise CommandError(f"Unknown Chapter slug: {options['chapter']}") from exc

        result = CorpusImporter().import_mistral_ocr(
            CorpusImportRequest(
                chapter=chapter,
                canonical_json_path=path,
                source_file_name=options["source_file_name"],
                source_hash=options["source_hash"],
                extractor_name="MistralOCR",
                extractor_version=options["extractor_version"],
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {result.element_count} stable TextbookElements "
                f"for {chapter.slug}."
            )
        )
