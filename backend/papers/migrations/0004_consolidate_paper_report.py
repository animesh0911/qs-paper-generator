from django.db import migrations, models


def forward(apps, schema_editor):
    Paper = apps.get_model("papers", "Paper")
    for paper in Paper.objects.all():
        paper.report = {
            "coverage": paper.coverage or {},
            "cog_coverage": paper.cog_coverage or {},
            "unfilled": paper.unfilled or [],
        }
        paper.save(update_fields=["report"])


def backward(apps, schema_editor):
    Paper = apps.get_model("papers", "Paper")
    for paper in Paper.objects.all():
        data = paper.report or {}
        paper.coverage = data.get("coverage", {})
        paper.cog_coverage = data.get("cog_coverage", {})
        paper.unfilled = data.get("unfilled", [])
        paper.save(update_fields=["coverage", "cog_coverage", "unfilled"])


class Migration(migrations.Migration):

    dependencies = [
        ("papers", "0003_paper_cog_coverage_paper_coverage_paper_unfilled"),
    ]

    operations = [
        migrations.AddField(
            model_name="paper",
            name="report",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.RunPython(forward, backward),
        migrations.RemoveField(model_name="paper", name="coverage"),
        migrations.RemoveField(model_name="paper", name="cog_coverage"),
        migrations.RemoveField(model_name="paper", name="unfilled"),
    ]
