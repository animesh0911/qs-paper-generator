"""A throwaway LangGraph ``StateGraph`` proving the checkpointer round-trips.

This is the walking-skeleton graph for the LangGraph migration (ADR-0005): it
carries no LLM call and no business logic — its only job is to exercise the
runtime end-to-end so later slices (generate->verify, AI editor, bulk-gen) build
on a proven foundation. The single ``ping`` node appends to a list reduced with
``operator.add``; with a ``PostgresSaver`` attached, a second invocation on the
same ``thread_id`` appends to the *persisted* list rather than starting fresh,
which is how a test observes resume-from-checkpoint.

Patterns / invariants:
- ``build_skeleton_graph`` takes the checkpointer as an argument (the injection
  seam — no module global), mirroring ``Ingestor(extractor=...)``. This is what
  lets tests pass their own saver without module-level patching (Rules 9/11).

Where it fits:
- Calls into: ``workflows.checkpointer.get_checkpointer`` (supplied by caller).
"""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, StateGraph


class SkeletonState(TypedDict):
    visits: Annotated[list[str], operator.add]


def _ping(state: SkeletonState) -> dict:
    return {"visits": ["ping"]}


def build_skeleton_graph(checkpointer: BaseCheckpointSaver):
    """Compile the one-node skeleton graph against the given checkpointer."""
    graph = StateGraph(SkeletonState)
    graph.add_node("ping", _ping)
    graph.set_entry_point("ping")
    graph.add_edge("ping", END)
    return graph.compile(checkpointer=checkpointer)
