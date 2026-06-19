"""Persist bulk Question-generation batches and review candidates."""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("bank", "0016_add_ai_generated_source_type"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="GenerationBatch",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("topic_names", models.JSONField(blank=True, default=list)),
                (
                    "difficulty_preset",
                    models.CharField(default="balanced", max_length=40),
                ),
                ("requested_count", models.PositiveSmallIntegerField(default=10)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("queued", "Queued"),
                            ("generating_questions", "Generating Questions"),
                            ("validating", "Validating"),
                            ("ready_for_review", "Ready for review"),
                            ("accepted", "Accepted"),
                            ("failed", "Failed"),
                            ("expired", "Expired"),
                        ],
                        db_index=True,
                        default="queued",
                        max_length=24,
                    ),
                ),
                ("error", models.TextField(blank=True)),
                ("ready_at", models.DateTimeField(blank=True, null=True)),
                ("accepted_at", models.DateTimeField(blank=True, null=True)),
                ("expired_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "chapters",
                    models.ManyToManyField(
                        related_name="generation_batches", to="bank.chapter"
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="generation_batches",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "school",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="generation_batches",
                        to="accounts.school",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="GeneratedQuestionCandidate",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("ready_for_review", "Ready for review"),
                            ("accepted", "Accepted"),
                            ("expired", "Expired"),
                        ],
                        db_index=True,
                        default="ready_for_review",
                        max_length=24,
                    ),
                ),
                ("payload", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("accepted_at", models.DateTimeField(blank=True, null=True)),
                (
                    "batch",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="candidates",
                        to="bank.generationbatch",
                    ),
                ),
                (
                    "question",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="generated_candidates",
                        to="bank.question",
                    ),
                ),
            ],
            options={
                "ordering": ["id"],
            },
        ),
    ]
