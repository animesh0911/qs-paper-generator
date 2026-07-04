"""Seed committed canonical NCERT textbook corpus artifacts for local dev."""

from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from bank.models import Chapter
from corpus.importer import CorpusImporter, CorpusImportRequest

JESC104_SOURCE_HASH = "efbb053ea8cedf29bc6891834613fdbcc17772e369f6b35405f3bb4701c41abe"
JESC110_SOURCE_HASH = "c8ed49fa55eedeb9ee5d5fbfa6d02061adb94075e94a32ca9bd16f4caf67c423"
REPO_ROOT = Path(__file__).resolve().parents[4]
CONTENT_ROOTS = (Path("/content"), REPO_ROOT / "content")

TEXTBOOK_ARTIFACTS = [
    {
        "chapter_slug": "carbon-and-its-compounds",
        "canonical_json_relpath": Path("ncert/jesc104/jesc104.json"),
        "source_file_name": "jesc104.pdf",
        "source_hash": JESC104_SOURCE_HASH,
        "extractor_name": "Docling",
        "extractor_version": "2.102.1",
        "required": True,
    },
    {
        "chapter_slug": "human-eye-and-the-colourful-world",
        "canonical_json_relpath": Path("ncert/jesc110/jesc110.json"),
        "source_file_name": "jesc110.pdf",
        "source_hash": JESC110_SOURCE_HASH,
        "extractor_name": "MistralOCR",
        "extractor_version": "mistral-ocr-latest",
        "required": False,
    },
]


def resolve_content_path(relpath: Path) -> Path:
    """Resolve Docker's /content mount, with a host-side repo fallback for tests."""
    for root in CONTENT_ROOTS:
        path = root / relpath
        if path.is_file():
            return path
    checked = ", ".join(str(root / relpath) for root in CONTENT_ROOTS)
    raise CommandError(f"Canonical textbook JSON not found. Checked: {checked}")


class Command(BaseCommand):
    help = "Seed committed NCERT textbook corpus artifacts used by topic generation."

    def handle(self, *args, **options):
        imported = 0
        for artifact in TEXTBOOK_ARTIFACTS:
            try:
                path = resolve_content_path(artifact["canonical_json_relpath"])
            except CommandError:
                if artifact.get("required", True):
                    raise
                self.stdout.write(
                    self.style.WARNING(
                        f"Skipping optional textbook corpus artifact: "
                        f"{artifact['canonical_json_relpath']}"
                    )
                )
                continue
            try:
                chapter = Chapter.objects.get(slug=artifact["chapter_slug"])
            except Chapter.DoesNotExist as exc:
                raise CommandError(
                    f"Unknown Chapter slug: {artifact['chapter_slug']}"
                ) from exc

            request = CorpusImportRequest(
                chapter=chapter,
                canonical_json_path=path,
                source_file_name=artifact["source_file_name"],
                source_hash=artifact["source_hash"],
                extractor_name=artifact["extractor_name"],
                extractor_version=artifact["extractor_version"],
            )
            importer = CorpusImporter()
            if artifact["extractor_name"] == "MistralOCR":
                result = importer.import_mistral_ocr(request)
            else:
                result = importer.import_document(request)
            imported += 1
            self.stdout.write(
                f"{chapter.slug}: imported {result.element_count} textbook elements."
            )

        self.stdout.write(
            self.style.SUCCESS(f"Seeded {imported} textbook corpus artifact(s).")
        )
