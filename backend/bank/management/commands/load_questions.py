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

``parse_quality`` is set here from the question's structure via
``question_shape.compute_parse_quality`` (no source-text verification pass —
ADR-0004). A
legacy ``source_text`` field, if present, is ignored. ``source_pdf`` feeds
``_parse_source_filename`` for provenance (year from the parent dir name).

Run as ``python manage.py load_questions content/parsed/``. Idempotent: rows are
de-duplicated by ``source_hash`` exactly like ``Ingestor.ingest``, so wiping the
DB and reloading the committed JSON reproduces the same bank. A malformed file
is reported and skipped — it does not abort the batch.
"""

from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from bank.ingestor import (
    Ingestor,
    _fingerprint,
    _parse_source_filename,
    _Provenance,
)
from bank.models import Chapter, Question
from bank.question_shape import compute_parse_quality


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
    def _load_file(path: Path, chapter_by_slug: dict[str, Chapter]) -> tuple[int, int]:
        """Load one committed JSON file into Question rows. Returns (created, skipped).

        Mirrors ``Ingestor.ingest`` from ``parse_quality`` onward: extraction and
        tagging already happened offline, so this picks up the reviewed dicts,
        sets parse_quality from structure, then dedups and persists. Files are
        processed one at a time and persisted before the next, so cross-file
        duplicates are caught via the DB ``source_hash`` lookup just like
        within-file ones.
        """
        data = json.loads(path.read_text())
        if not isinstance(data, dict):
            raise ValueError("top-level JSON must be an object")
        source_pdf = data["source_pdf"]
        questions = data["questions"]
        if not isinstance(questions, list):
            raise ValueError("'questions' must be a list")

        # Structural self-assessment — no source-text verification (ADR-0004).
        for q in questions:
            q["parse_quality"] = compute_parse_quality(q, q.get("qtype", ""))

        prov = _parse_source_filename(Path(source_pdf))
        provenance = _Provenance(
            source_type=prov["source_type"],
            source_name=prov["source_name"],
            source_file_name=prov["source_file_name"],
        )

        # De-duplication: skip questions already in the bank AND repeats within
        # this file — identical to Ingestor.ingest.
        all_fingerprints = [_fingerprint(q["text"]) for q in questions]
        seen = set(
            Question.objects.filter(source_hash__in=all_fingerprints).values_list(
                "source_hash", flat=True
            )
        )
        unique_indices: list[int] = []
        for i, fp in enumerate(all_fingerprints):
            if fp in seen:
                continue
            seen.add(fp)
            unique_indices.append(i)
        skipped = len(questions) - len(unique_indices)
        rows = [questions[i] for i in unique_indices]
        fingerprints = [all_fingerprints[i] for i in unique_indices]
        if not rows:
            return 0, skipped

        # No PDF in hand → no diagram cropping; committed content keeps whatever
        # image/image_placeholder items it already carries. _persist still flags
        # has_diagram from primary_form, the question text, and those items.
        primary_assets: list[str | None] = [None] * len(rows)
        created = Ingestor._persist(
            rows, fingerprints, primary_assets, chapter_by_slug, provenance
        )
        return created, skipped
