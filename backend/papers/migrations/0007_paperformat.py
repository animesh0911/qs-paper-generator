from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("papers", "0006_questionusage"),
    ]

    operations = [
        migrations.CreateModel(
            name="PaperFormat",
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
                ("format_id", models.SlugField(max_length=100, unique=True)),
                ("name", models.CharField(max_length=255)),
                ("preset_name", models.CharField(max_length=50)),
                ("page", models.JSONField()),
                ("layout", models.JSONField()),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={
                "ordering": ["name"],
            },
        ),
    ]
