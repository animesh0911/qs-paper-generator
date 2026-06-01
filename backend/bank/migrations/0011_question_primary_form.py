from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bank", "0010_rewrite_qtype_values"),
    ]

    operations = [
        migrations.AddField(
            model_name="question",
            name="primary_form",
            field=models.CharField(
                blank=True,
                choices=[
                    ("none", "None"),
                    ("diagram_based", "Diagram-based"),
                    ("table_based", "Table-based"),
                ],
                default="none",
                max_length=16,
            ),
        ),
    ]
