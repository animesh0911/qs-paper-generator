"""Import one existing canonical Docling extraction without running Docling.

The command is the developer-populated NCERT corpus front door. It normalizes
an already-produced Docling JSON artifact and atomically replaces the matching
TextbookDocument's elements, making repeated imports deterministic and safe.
"""

from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from bank.models import Chapter
from corpus.importer import CorpusImporter, CorpusImportRequest


class Command(BaseCommand):
    help = "Import an existing canonical Docling JSON file into TextbookElements."

    def add_arguments(self, parser):
        parser.add_argument("json_path", type=Path)
        parser.add_argument("--chapter", required=True, help="Canonical Chapter slug.")
        parser.add_argument("--source-file-name", default="jesc104.pdf")
        parser.add_argument("--source-hash", required=True)
        parser.add_argument("--extractor-version", default="2.102.1")

    def handle(self, *args, **options):
        path: Path = options["json_path"]
        if not path.is_file():
            raise CommandError(f"Canonical Docling JSON not found: {path}")
        try:
            chapter = Chapter.objects.get(slug=options["chapter"])
        except Chapter.DoesNotExist as exc:
            raise CommandError(f"Unknown Chapter slug: {options['chapter']}") from exc

        result = CorpusImporter().import_document(
            CorpusImportRequest(
                chapter=chapter,
                canonical_json_path=path,
                source_file_name=options["source_file_name"],
                source_hash=options["source_hash"],
                extractor_name="Docling",
                extractor_version=options["extractor_version"],
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {result.element_count} stable TextbookElements "
                f"for {chapter.slug}."
            )
        )
