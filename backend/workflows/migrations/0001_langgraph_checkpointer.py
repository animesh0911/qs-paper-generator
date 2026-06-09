"""Data migration: create the LangGraph ``PostgresSaver`` checkpoint tables.

ADR-0006 puts LangGraph's execution-state checkpointer in the *same* Postgres as
the business job ledger — "one ``.setup()`` call / migration, no new datastore."
This runs that one call: it opens a psycopg connection to the database alias
being migrated and lets ``PostgresSaver.setup()`` create (and version) its own
``checkpoints*`` tables.

Why a separate connection rather than ``schema_editor``: ``PostgresSaver`` drives
its setup over a raw psycopg connection in autocommit mode (its own migration
ledger commits per step), which ``from_conn_string`` provides — Django's
schema-editor connection runs inside the migration's managed transaction and is
the wrong shape for it. Deriving the conn string from the live
``schema_editor.connection.settings_dict`` keeps it pointed at whichever database
is being migrated, so pytest builds the tables into ``test_qpg`` automatically.

Reverse is a noop: the checkpoint tables are infrastructure (and ``setup()`` is
idempotent), not app data, so a rollback leaves them in place.
"""

from django.db import migrations

from workflows.checkpointer import conn_string


def setup_checkpoint_tables(apps, schema_editor):
    from langgraph.checkpoint.postgres import PostgresSaver

    with PostgresSaver.from_conn_string(
        conn_string(schema_editor.connection.settings_dict)
    ) as checkpointer:
        checkpointer.setup()


class Migration(migrations.Migration):

    dependencies = []

    operations = [
        migrations.RunPython(setup_checkpoint_tables, migrations.RunPython.noop),
    ]
