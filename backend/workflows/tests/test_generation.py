"""Resumable-generation tests: kill a run after the model call, never re-bill.

These prove the payoff of putting bulk generation on a ``StateGraph`` (mirroring
``test_extraction``): the single paid ``generate`` call is checkpointed, so a
crash in the ``validate_and_persist`` tail resumes from that checkpoint and the
generator is asked for candidates exactly once (Rule 13). The generator is a
fake that counts calls; the checkpointer is the real ``PostgresSaver`` against
the test database, so two ``get_checkpointer()`` blocks stand in for the killed
process and the later cron pass.
"""

from __future__ import annotations

import uuid

import pytest

from bank.models import (
    Chapter,
    GeneratedQuestionCandidate,
    GenerationBatch,
)
from workflows import generation as generation_mod
from workflows.checkpointer import get_checkpointer
from workflows.generation import build_generation_graph

pytestmark = pytest.mark.django_db


def _valid_payload():
    return {
        "chapter_slug": "life-processes",
        "qtype": "mcq",
        "marks": 1,
        "cognitive_level": "R",
        "raw_text": "Which process releases energy from glucose?",
        "content": {
            "stem": [{"type": "paragraph", "text": "Which process releases energy?"}],
            "options": [
                {"label": "A", "content": [{"type": "paragraph", "text": "Respire"}]},
                {"label": "B", "content": [{"type": "paragraph", "text": "Osmosis"}]},
                {"label": "C", "content": [{"type": "paragraph", "text": "Diffuse"}]},
                {"label": "D", "content": [{"type": "paragraph", "text": "Excrete"}]},
            ],
        },
        "topic_names": ["Nutrition"],
        "answer": "A. Respiration",
        "question_citation_ids": ["chunk-respiration"],
        "answer_citation_ids": ["chunk-respiration"],
        "source": {"type": "ai_generated", "name": "question-generation"},
    }


class CountingGenerator:
    """A ``QuestionGenerator`` that records how many times it was billed."""

    def __init__(self, payloads):
        self._payloads = payloads
        self.calls = 0

    def generate(self, request):
        self.calls += 1
        return list(self._payloads)


def _batch():
    batch = GenerationBatch.objects.create(requested_count=1)
    batch.chapters.set([Chapter.objects.get(slug="life-processes")])
    return batch


def _cfg(thread_id):
    return {"configurable": {"thread_id": thread_id}}


def test_resume_after_persist_crash_does_not_rebill_the_model(monkeypatch):
    """A crash in validate_and_persist resumes from the post-generate checkpoint:
    the generator is billed once across both passes, and candidates persist."""
    batch = _batch()
    thread_id = uuid.uuid4().hex
    generator = CountingGenerator([_valid_payload()])

    # First pass: the model call succeeds and checkpoints, then persist dies.
    real_validate = generation_mod.validate_generated_questions
    monkeypatch.setattr(
        generation_mod,
        "validate_generated_questions",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("killed in persist")),
    )
    with get_checkpointer() as checkpointer:
        graph = build_generation_graph(
            checkpointer,
            generator_factory=lambda: generator,
            context_assembler_factory=lambda: None,
        )
        with pytest.raises(RuntimeError, match="killed in persist"):
            graph.invoke({"batch_id": batch.pk}, _cfg(thread_id), durability="sync")
    assert generator.calls == 1
    assert GeneratedQuestionCandidate.objects.count() == 0

    # Second pass: a fresh process resumes the thread; generate is NOT re-run.
    monkeypatch.setattr(generation_mod, "validate_generated_questions", real_validate)
    with get_checkpointer() as checkpointer:
        graph = build_generation_graph(
            checkpointer,
            generator_factory=lambda: generator,
            context_assembler_factory=lambda: None,
        )
        final = graph.invoke(None, _cfg(thread_id), durability="sync")

    assert generator.calls == 1  # the paid call was never repeated
    assert final["valid_count"] == 1
    assert GeneratedQuestionCandidate.objects.filter(batch=batch).count() == 1
