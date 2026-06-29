"""Apply committed bank overrides (answers, disabled flags) after loading questions."""

from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from bank.models import AnswerSource, Question


class Command(BaseCommand):
    help = "Apply committed question-bank overrides from JSON."

    def add_arguments(self, parser):
        parser.add_argument("path", type=str, help="Path to question_overrides.json")

    def handle(self, *args, **options):
        path = Path(options["path"])
        if not path.is_file():
            raise CommandError(f"Not a file: {path}")

        data = json.loads(path.read_text())
        overrides = data.get("overrides")
        if not isinstance(overrides, list):
            raise CommandError("JSON must contain an 'overrides' list")

        by_hash = {
            q.source_hash: q
            for q in Question.objects.exclude(source_hash="")
            if q.source_hash
        }
        by_text = {q.text: q for q in Question.objects.all()}

        updated = unmatched = 0
        for item in overrides:
            if not isinstance(item, dict):
                unmatched += 1
                continue
            q = None
            source_hash = item.get("source_hash")
            if source_hash:
                q = by_hash.get(source_hash)
            if q is None:
                text = item.get("text")
                if text:
                    q = by_text.get(text)
            if q is None:
                unmatched += 1
                continue

            fields: list[str] = []
            if "answer" in item:
                q.answer = str(item.get("answer") or "")
                q.answer_source = (
                    AnswerSource.GENERATED_UNVERIFIED if q.answer else ""
                )
                fields += ["answer", "answer_source"]
            if "parse_quality" in item:
                q.parse_quality = item["parse_quality"]
                fields.append("parse_quality")
            if "review_flags" in item:
                q.review_flags = list(item.get("review_flags") or [])
                fields.append("review_flags")

            if fields:
                q.save(update_fields=sorted(set(fields)))
                updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Applied {updated} override(s); {unmatched} unmatched."
            )
        )
