"""Walking-skeleton tests: the LangGraph runtime durably persists and resumes.

These prove the foundation ADR-0005/ADR-0006 rests on — that a compiled
``StateGraph`` checkpoints to the existing Postgres and resumes a thread whose
state lives only in the database. If they pass, every later durable/HITL slice
can rely on cross-process pause/resume instead of re-deriving it. If the
checkpointer were silently in-memory (a ``MemorySaver`` regression) or the
checkpoint tables were missing, the resume test would fail — which is the point.

The checkpointer is injected into ``build_skeleton_graph``; nothing here patches
a module global (Rules 9/11).
"""

from __future__ import annotations

import uuid

import pytest

from workflows.checkpointer import get_checkpointer
from workflows.skeleton import build_skeleton_graph

pytestmark = pytest.mark.django_db


def _cfg(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


def test_checkpoint_is_written_keyed_by_thread_id():
    """A run persists state under its thread_id and leaves other threads empty.

    The keying matters because ADR-0006 has the cron-drain resume a specific
    job by its thread_id pointer — state must not bleed across threads.
    """
    thread_id = str(uuid.uuid4())
    other_thread_id = str(uuid.uuid4())

    with get_checkpointer() as checkpointer:
        graph = build_skeleton_graph(checkpointer)
        graph.invoke({"visits": ["call-1"]}, _cfg(thread_id))

        persisted = graph.get_state(_cfg(thread_id))
        assert persisted.values["visits"] == ["call-1", "ping"]

        # A thread that was never invoked has no persisted checkpoint.
        untouched = graph.get_state(_cfg(other_thread_id))
        assert untouched.values == {}


def test_resume_loads_prior_state_from_postgres():
    """A fresh saver + graph resumes a thread whose state is only in Postgres.

    Two independent ``get_checkpointer()`` blocks share nothing in memory — the
    second builds a brand-new connection and a brand-new compiled graph. This
    stands in for ADR-0006's cross-process resume (a later drain pass / request
    in another process): if the prior "call-1" run is visible to the second
    invocation, it could only have come from the durable checkpoint, not from
    in-process state.
    """
    thread_id = str(uuid.uuid4())

    with get_checkpointer() as checkpointer:
        graph = build_skeleton_graph(checkpointer)
        graph.invoke({"visits": ["call-1"]}, _cfg(thread_id))

    with get_checkpointer() as fresh_checkpointer:
        fresh_graph = build_skeleton_graph(fresh_checkpointer)
        result = fresh_graph.invoke({"visits": ["call-2"]}, _cfg(thread_id))

    # The reducer appended call-2 onto the resumed state, so the first run's
    # contributions survive ahead of the second's — proof of resume.
    assert result["visits"] == ["call-1", "ping", "call-2", "ping"]


def test_builder_uses_the_injected_checkpointer():
    """The graph carries the passed saver — the no-module-patching seam.

    If a future change reintroduced a module-level checkpointer, this would
    fail, guarding the injection contract that keeps tests honest (Rules 9/11).
    """
    with get_checkpointer() as checkpointer:
        graph = build_skeleton_graph(checkpointer)
        assert graph.checkpointer is checkpointer
