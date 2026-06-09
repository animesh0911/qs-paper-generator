"""Shared LangGraph ``PostgresSaver`` factory over the existing Postgres.

This is the execution-state seam from ADR-0006: LangGraph checkpoints (the
engine-internal snapshot that makes a graph resumable across processes and lets
it pause for human review) live in the *same* Postgres as the business job
ledger — no new datastore, no Celery/Redis (#105). The checkpoint tables are
created once by the data migration in this app, which calls the same
``PostgresSaver.setup()`` this factory's connection talks to.

Patterns / invariants:
- The connection string is derived from the *live* Django connection's
  ``settings_dict``, not the static ``DATABASES`` literal — so under pytest the
  saver follows the test database (``test_qpg``) automatically.
- ``get_checkpointer()`` is a context manager: callers open it around an
  ``invoke``/resume and the psycopg connection is closed on exit. The
  checkpointer is never a module global, so graph builders take it as an
  argument (no module-level patching in tests — Rules 9/11).

Where it fits:
- Called by: workflows graph builders (e.g. ``workflows.skeleton``) and the
  data migration ``0001_langgraph_checkpointer``.
- Persisted via: LangGraph ``PostgresSaver`` checkpoint tables.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from django.db import connection
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.conninfo import make_conninfo


def conn_string(settings_dict: dict) -> str:
    """Build a libpq conninfo string from a Django DB ``settings_dict``.

    Uses ``make_conninfo`` rather than hand-formatting a URI so credentials with
    special characters (``@ : / ?`` — common in generated production passwords)
    are escaped correctly instead of corrupting the host/password boundary.
    """
    return make_conninfo(
        host=settings_dict["HOST"],
        port=settings_dict["PORT"],
        user=settings_dict["USER"],
        password=settings_dict["PASSWORD"],
        dbname=settings_dict["NAME"],
    )


@contextmanager
def get_checkpointer() -> Iterator[PostgresSaver]:
    """Yield a ``PostgresSaver`` bound to the default alias' current database."""
    with PostgresSaver.from_conn_string(
        conn_string(connection.settings_dict)
    ) as checkpointer:
        yield checkpointer
