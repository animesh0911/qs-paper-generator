"""load_questions — deterministic, no-key ingestion from committed JSON.

The no-API-key ingestion entry point. Where the LLM pipeline (``Ingestor``)
parses a PDF and tags it at runtime via the LLM seams, this command loads
question dicts that were already parsed (``RegexSegmenter``) and tagged offline,
then reviewed and committed to ``content/parsed/``. It runs the *same*
guardrails and persistence as the LLM path, so both produce identical row
shapes (see #54).

Each input file is one source PDF's worth of questions::

    {
      "source_pdf": "science_2024/31_1_1_Science.pdf",
      "source_text": "<cleaned paper text, the strip_hindi blob>",
      "questions": [ {section, qtype, marks, text, options, content,
                      chapter_slug, cognitive_level, topic_names,
                      primary_form}, ... ]
    }

``source_text`` is the cleaned paper blob the questions were segmented from. It
travels in the file so ``_verify`` can do real fidelity/coverage/order work
against the genuine paper — not a reconstruction. ``source_pdf`` feeds
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
    _verify,
)
from bank.models import Chapter, Question


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

        Mirrors ``Ingestor.ingest`` from ``_verify`` onward: the parse and tag
        steps already happened offline, so this picks up the reviewed dicts and
        runs verification → dedup → persist. Files are processed one at a time
        and persisted before the next, so cross-file duplicates are caught via
        the DB ``source_hash`` lookup just like within-file ones.
        """
        data = json.loads(path.read_text())
        if not isinstance(data, dict):
            raise ValueError("top-level JSON must be an object")
        source_pdf = data["source_pdf"]
        source_text = data.get("source_text", "")
        questions = data["questions"]
        if not isinstance(questions, list):
            raise ValueError("'questions' must be a list")

        # Guardrail: score the reviewed dicts against the real paper text before
        # trusting them, setting parse_quality (fidelity/coverage/order, ADR-0003).
        verified = _verify(questions, source_text)

        prov = _parse_source_filename(Path(source_pdf))
        provenance = _Provenance(
            source_type=prov["source_type"],
            source_name=prov["source_name"],
            source_file_name=prov["source_file_name"],
        )

        # De-duplication: skip questions already in the bank AND repeats within
        # this file — identical to Ingestor.ingest.
        all_fingerprints = [_fingerprint(q["text"]) for q in verified]
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
        skipped = len(verified) - len(unique_indices)
        rows = [verified[i] for i in unique_indices]
        fingerprints = [all_fingerprints[i] for i in unique_indices]
        if not rows:
            return 0, skipped

        # No PDF in hand → no diagram extraction; _persist still flags
        # has_diagram from primary_form and the question text.
        diagram_bytes_list: list[bytes | None] = [None] * len(rows)
        created = Ingestor._persist(
            rows, fingerprints, diagram_bytes_list, chapter_by_slug, provenance
        )
        return created, skipped
