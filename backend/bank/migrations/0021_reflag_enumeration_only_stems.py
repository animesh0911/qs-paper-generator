"""Backfill the two stem defects the ingest door now handles.

1. Re-flag questions whose flat ``text`` is only enumeration scaffolding
   ("37.", "(b)") as ``empty_stem`` → ``broken`` (mirrors the stronger
   ``bank.guardrails._stem_flag``). These are unusable fragments the bank view
   now hides.
2. Repair questions whose structured ``content.stem`` lost its body to a bare
   label ("(b)", "39. (a)") while the full question survived in ``text`` —
   rebuild the stem from ``text`` (mirrors ``bank.question_content.repair_stem``)
   so the renderer stops showing the fragment.

Idempotent: re-running matches the same rows, the flag set is a set, and an
already-repaired stem no longer flattens to a label.
"""

import re

from django.db import migrations

# Frozen copies of bank.guardrails / bank.question_content regexes so this
# migration is unaffected by later edits to those modules.
_ENUMERATION_ONLY_RE = re.compile(
    r"^(?:\s*(?:\d{1,3}[.):]?|\(\s*[a-z0-9ivxlcdm]{1,4}\s*\)))+\s*$",
    re.IGNORECASE,
)

FLAG_EMPTY_STEM = "empty_stem"


def _is_contentless(value):
    stripped = (value or "").strip()
    return not stripped or bool(_ENUMERATION_ONLY_RE.match(stripped))


def _flatten_stem(content):
    stem = (content or {}).get("stem")
    if not isinstance(stem, list):
        return ""
    return " ".join(
        str(it.get("text", "")) for it in stem if isinstance(it, dict)
    ).strip()


def backfill(apps, schema_editor):
    Question = apps.get_model("bank", "Question")
    for question in Question.objects.iterator():
        text = (question.text or "").strip()
        changed_fields = []

        # 1. Whole-text fragment → broken.
        if question.parse_quality != "broken" and _is_contentless(text):
            flags = list(question.review_flags or [])
            if FLAG_EMPTY_STEM not in flags:
                flags.append(FLAG_EMPTY_STEM)
                question.review_flags = flags
                changed_fields.append("review_flags")
            question.parse_quality = "broken"
            changed_fields.append("parse_quality")
            question.save(update_fields=changed_fields)
            continue

        # 2. Defective structured stem, real text → rebuild stem from text.
        if (
            _is_contentless(_flatten_stem(question.content))
            and text
            and not _is_contentless(text)
        ):
            content = dict(question.content or {})
            content["stem"] = [{"type": "paragraph", "text": text}]
            question.content = content
            question.save(update_fields=["content"])


def noop(apps, schema_editor):
    """No safe reverse — we cannot reconstruct the pre-migration shapes."""


class Migration(migrations.Migration):
    dependencies = [
        ("bank", "0020_generationbatch_discarded_at_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill, noop),
    ]
