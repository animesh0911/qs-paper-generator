"""load_questions — deterministic, no-key ingestion from committed JSON.

The no-API-key ingestion entry point. Where the LLM pipeline (``Ingestor``)
sends a PDF to Gemini and tags it at runtime, this command loads question dicts
that were extracted, tagged, reviewed, and committed to ``content/parsed/``
offline. It runs the *same* persistence as the LLM path, so both produce
identical row shapes (see #54).

Each input file is one source PDF's worth of questions::

    {
      "source_pdf": "science_2024/31_1_1_Science.pdf",
      "questions": [ {section, qtype, marks, text, options, content,
                      chapter_slug, cognitive_level, topic_names,
                      primary_form, parse_quality?}, ... ]
    }

``parse_quality`` is set from the question's structure by the same
``Ingestor._ingest_raw`` tail the live Gemini path runs (no source-text
verification pass — ADR-0004). A
legacy ``source_text`` field, if present, is ignored. ``source_pdf`` feeds
``_parse_source_filename`` for provenance (year from the parent dir name).

Run as ``python manage.py load_questions /content/parsed/`` (Docker) or
``python manage.py load_questions ../content/parsed/`` (host). Idempotent: rows are
de-duplicated by ``source_hash`` exactly like ``Ingestor.ingest``, so wiping the
DB and reloading the committed JSON reproduces the same bank. A malformed file
is reported and skipped — it does not abort the batch.
"""

from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from bank.ingestor import Ingestor, _parse_source_filename, _Provenance
from bank.models import Chapter


class Command(BaseCommand):
    help = "Load committed structured-question JSON files into the bank (no LLM)."

    def add_arguments(self, parser):
        parser.add_argument(
            "directory",
            type=str,
            help="Directory of per-source-PDF *.json files to load.",
        )

    def handle(self, *args, **options):
        directory = Path(options["directory"])
        if not directory.is_dir():
            raise CommandError(f"Not a directory: {directory}")

        json_files = sorted(directory.glob("*.json"))
        if not json_files:
            self.stdout.write(f"No JSON files found in {directory}.")
            return

        # Diagrams committed by extract_paper live in <dir>/assets/ and are
        # referenced by the questions' content as "diagrams/<name>". Copy them
        # into default_storage so the renderer can serve them — the committed
        # JSON is otherwise inert (no PDF in hand at load time, ADR-0004).
        rehydrated = self._rehydrate_assets(directory / "assets")
        if rehydrated:
            self.stdout.write(f"Re-hydrated {rehydrated} diagram asset(s).")

        # Resolved once: chapter slugs are a fixed taxonomy (migration 0003).
        chapter_by_slug = {c.slug: c for c in Chapter.objects.all()}

        total_created = total_skipped = total_failed = 0
        for path in json_files:
            # One bad file must not abort the batch — report and move on.
            try:
                created, skipped = self._load_file(path, chapter_by_slug)
            except Exception as exc:  # noqa: BLE001
                total_failed += 1
                self.stderr.write(self.style.ERROR(f"Skipped {path.name}: {exc}"))
                continue
            total_created += created
            total_skipped += skipped
            self.stdout.write(
                f"{path.name}: {created} created, {skipped} duplicate(s) skipped."
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Load complete: {total_created} created, {total_skipped} "
                f"duplicate(s) skipped, {total_failed} file(s) failed."
            )
        )

    @staticmethod
    def _rehydrate_assets(assets_dir: Path) -> int:
        """Copy committed crop PNGs into default_storage under ``diagrams/``.

        Idempotent: an asset already present (its exact storage name) is left
        alone, so re-running the loader neither duplicates files nor drifts the
        ``assetId`` the content references. Returns the number copied this run.
        """
        if not assets_dir.is_dir():
            return 0
        from django.core.files.base import ContentFile
        from django.core.files.storage import default_storage

        copied = 0
        for png in sorted(assets_dir.glob("*.png")):
            target = f"diagrams/{png.name}"
            if default_storage.exists(target):
                continue
            default_storage.save(target, ContentFile(png.read_bytes()))
            copied += 1
        return copied

    @staticmethod
    def _load_file(path: Path, chapter_by_slug: dict[str, Chapter]) -> tuple[int, int]:
        """Load one committed JSON file into Question rows. Returns (created, skipped).

        Reads the reviewed dicts (extraction and tagging already happened
        offline) and hands them to ``Ingestor._ingest_raw`` — the same
        quality/guardrail/dedup/persist tail the live Gemini path runs
        (``pdf_bytes=None``: no PDF in hand, so no cropping; committed content
        keeps whatever image/image_placeholder items it already carries).
        Files are processed one at a time and persisted before the next, so
        cross-file duplicates are caught via the DB ``source_hash`` lookup
        just like within-file ones.
        """
        data = json.loads(path.read_text())
        if not isinstance(data, dict):
            raise ValueError("top-level JSON must be an object")
        source_pdf = data["source_pdf"]
        questions = data["questions"]
        if not isinstance(questions, list):
            raise ValueError("'questions' must be a list")

        prov = _parse_source_filename(Path(source_pdf))
        provenance = _Provenance(
            source_type=prov["source_type"],
            source_name=prov["source_name"],
            source_file_name=prov["source_file_name"],
        )

        result = Ingestor()._ingest_raw(
            questions,
            provenance=provenance,
            school=None,
            pdf_bytes=None,
            chapter_by_slug=chapter_by_slug,
        )
        return result.created, result.skipped_duplicates
