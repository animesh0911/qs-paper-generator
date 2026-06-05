from django.core.management import call_command
from django.db import migrations


def create_cache_table(apps, schema_editor):
    # Creates the ``qpg_cache`` table backing Django's DatabaseCache
    # (settings.CACHES). Idempotent: skips if the table already exists.
    call_command("createcachetable", database=schema_editor.connection.alias)


class Migration(migrations.Migration):
    dependencies = [
        ("papers", "0008_seed_paperformat"),
    ]

    operations = [
        migrations.RunPython(create_cache_table, migrations.RunPython.noop),
    ]
