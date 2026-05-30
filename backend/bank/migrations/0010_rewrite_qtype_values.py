"""Data migration: rewrite legacy QuestionType values to PaperDocumentV1 strings.

Old enum values (MCQ/VSA/SA/LA/CASE) are rewritten in place to the contract
strings (mcq/very_short_answer/short_answer/long_answer/case_based) so DB and
contract share a single source of truth. See ADR-0001.

Reversible: the reverse migration restores the old short codes. Existing rows
in dev DBs (~11 seeded) are updated; in CI this is a no-op since fresh DBs
start from the new seed_questions which already uses the new values.
"""
from django.db import migrations


FORWARD = {
    "MCQ": "mcq",
    "VSA": "very_short_answer",
    "SA": "short_answer",
    "LA": "long_answer",
    "CASE": "case_based",
}


def forward(apps, schema_editor):
    Question = apps.get_model("bank", "Question")
    for old, new in FORWARD.items():
        Question.objects.filter(qtype=old).update(qtype=new)


def reverse(apps, schema_editor):
    Question = apps.get_model("bank", "Question")
    for old, new in FORWARD.items():
        Question.objects.filter(qtype=new).update(qtype=old)


class Migration(migrations.Migration):

    dependencies = [
        ("bank", "0009_qtype_contract_strings"),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
