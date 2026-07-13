"""Scenario 3 — answer generation for extracted questions.

Production path under test: ``bank.answer_generation.BankAnswerGenerator
.generate`` — the exact object the answer graph's ``generate`` node calls. It
reads ``Question`` rows and returns answer dicts *without persisting*, so eval
runs never mutate bank data. Model routing rides ``LLM_ANSWER_GENERATION_*``.

Brief mapping:
- batch_size = number of extracted questions answered in one run (the brief's
  pages × questions/page, 250–2500 at the top end). Production answers one
  upload per call today; at eval scale the run chunks question ids and makes
  one production call per chunk — ``chunk_size`` is part of the matrix, since
  it is the real cost/latency/quality trade-off a premium tier would tune.
- outputs per run → model, cost, batch_size, latency, accuracy.
- accuracy → deterministic here: answered rate + corpus coverage (so
  ungrounded judging is never silently mixed in); textbook-grounded judged
  accuracy belongs to the deepeval suite's answers lane (#226), grading the
  same ``_judge_payload`` shape golden graders see.
"""

from __future__ import annotations

import argparse
from math import ceil
from typing import Any

from evals.budget import UnitEstimate
from evals.metering import Meter, metered_make_model, seam_env
from evals.records import RunRecord
from evals.registry import get_model
from evals.scenarios.base import (
    EvalNotImplemented,
    EvalUnit,
    load_artifact,
    new_record,
    save_artifact,
    settle_record,
    unit_wall,
)

SCENARIO = "answers"

# Rough per-chunk priors for the budget gate: ~140 prompt tokens per rendered
# question + parser format instructions; answers average ~80 output tokens.
_EST_INPUT_TOKENS_PER_QUESTION = 140
_EST_OUTPUT_TOKENS_PER_QUESTION = 80
_EST_PROMPT_OVERHEAD = 600


def build_units(args: argparse.Namespace) -> list[EvalUnit]:
    units = []
    for model_id in args.models:
        for chunk_size in args.chunk_sizes:
            for trial in range(args.trials):
                units.append(
                    EvalUnit(
                        scenario=SCENARIO,
                        arm="chunked",
                        model_eval_id=model_id,
                        config={
                            "ingestion_job_id": args.ingestion_job,
                            "questions_artifact": (
                                str(args.questions_artifact)
                                if getattr(args, "questions_artifact", None)
                                else None
                            ),
                            "question_limit": args.question_limit,
                            "chunk_size": chunk_size,
                        },
                        trial=trial,
                    )
                )
    return units


def estimate(unit: EvalUnit) -> UnitEstimate:
    questions = int(unit.config.get("question_limit") or 250)
    chunk = int(unit.config["chunk_size"])
    return UnitEstimate(
        label=unit.label,
        calls=ceil(questions / chunk),
        input_tokens_per_call=(
            _EST_PROMPT_OVERHEAD + _EST_INPUT_TOKENS_PER_QUESTION * chunk
        ),
        output_tokens_per_call=_EST_OUTPUT_TOKENS_PER_QUESTION * chunk,
    )


# ---------------------------------------------------------------------------
# Paid phase
# ---------------------------------------------------------------------------


def run_unit(unit: EvalUnit) -> RunRecord:
    """Chunked production answer generation from DB rows or a JSON artifact."""
    from ai_services.llm import ModelPurpose
    from bank.answer_generation import USABLE_PARSE_QUALITIES, BankAnswerGenerator
    from bank.answer_generation_core import AnswerGenerator, AnswerQuestion
    from bank.models import IngestionJob

    spec = get_model(unit.model_eval_id)
    record = new_record(unit, spec)
    meter = Meter(spec.model)

    job_id = unit.config.get("ingestion_job_id")
    artifact_path = unit.config.get("questions_artifact")
    if not job_id and not artifact_path:
        raise EvalNotImplemented(
            "Pass either --questions-artifact <json> (no DB) or --ingestion-job <id>."
        )

    limit = int(unit.config.get("question_limit") or 0)
    artifact_questions: list[dict[str, Any]] = []
    question_ids: list[int] = []
    if artifact_path:
        import json
        from pathlib import Path

        raw = json.loads(Path(str(artifact_path)).read_text())
        values = raw.get("questions") if isinstance(raw, dict) else raw
        if not isinstance(values, list):
            raise EvalNotImplemented(
                "Question artifact must be a list or {questions: [...]}"
            )
        for index, value in enumerate(values, start=1):
            if not isinstance(value, dict):
                continue
            item = dict(value)
            item.setdefault("id", index)
            artifact_questions.append(item)
        if limit:
            artifact_questions = artifact_questions[:limit]
        question_ids = [int(item["id"]) for item in artifact_questions]
    else:
        job = IngestionJob.objects.get(pk=job_id)
        question_ids = list(
            job.questions.filter(parse_quality__in=USABLE_PARSE_QUALITIES)
            .order_by("section", "id")
            .values_list("pk", flat=True)
        )
        if limit:
            question_ids = question_ids[:limit]

    if not question_ids:
        raise EvalNotImplemented("The selected source has no usable questions.")

    chunk_size = int(unit.config["chunk_size"])
    record.batch_size = len(question_ids)
    answers: list[dict] = []
    batch_diagnostics: list[dict[str, Any]] = []

    def collect_result(result, source_ids: list[int]) -> None:
        answers.extend(result.accepted)
        batch_diagnostics.append(
            {
                "question_ids": source_ids,
                "missing_ids": list(result.missing_ids),
                "duplicate_ids": list(result.duplicate_ids),
                "unexpected_ids": list(result.unexpected_ids),
                "blank_ids": list(result.blank_ids),
            }
        )

    with unit_wall(record):
        with seam_env(spec.env_overrides("answer_generation")):
            make_model = metered_make_model(meter)
            if artifact_questions:
                generator = AnswerGenerator(make_model(ModelPurpose.ANSWER_GENERATION))
                questions = [
                    AnswerQuestion.from_mapping(item) for item in artifact_questions
                ]
                for start in range(0, len(questions), chunk_size):
                    batch = questions[start : start + chunk_size]
                    collect_result(generator.generate(batch), [q.id for q in batch])
            else:
                generator = BankAnswerGenerator(make_model=make_model)
                for start in range(0, len(question_ids), chunk_size):
                    batch_ids = question_ids[start : start + chunk_size]
                    collect_result(generator.generate(batch_ids), batch_ids)

    record.delivered = len(answers)
    save_artifact(
        record,
        {
            "ingestion_job_id": job_id,
            "questions_artifact": artifact_path,
            "input_questions": artifact_questions,
            "question_ids": question_ids,
            "chunk_size": chunk_size,
            "answers": answers,
            "batch_diagnostics": batch_diagnostics,
        },
    )
    record.success = True
    return settle_record(record, meter, spec)


# ---------------------------------------------------------------------------
# Scoring phase
# ---------------------------------------------------------------------------


def score_unit(record: dict) -> dict[str, Any]:
    """Deterministic coverage metrics for one stored run.

    Judged accuracy belongs to the deepeval suite's answers lane (#226).
    """
    from bank.models import Question
    from evals.datasets.loaders import corpus_coverage

    artifact = load_artifact(record)
    answers: list[dict] = artifact.get("answers", [])
    question_ids = [int(item["id"]) for item in answers if item.get("id")]
    input_questions = artifact.get("input_questions") or []
    artifact_by_id = {
        int(item["id"]): item
        for item in input_questions
        if isinstance(item, dict) and item.get("id") is not None
    }
    questions = (
        {
            q.pk: q
            for q in Question.objects.filter(pk__in=question_ids).select_related(
                "chapter"
            )
        }
        if not artifact_by_id
        else {}
    )
    chapter_slugs = (
        [
            str(item.get("chapter_slug"))
            for item in artifact_by_id.values()
            if item.get("chapter_slug")
        ]
        if artifact_by_id
        else [q.chapter.slug for q in questions.values() if q.chapter]
    )

    return {
        "answered_rate": (
            len(answers) / record.get("batch_size", 1)
            if record.get("batch_size")
            else 0.0
        ),
        "corpus_coverage": corpus_coverage(chapter_slugs).fraction,
    }

def golden_items(record: dict, sample: int) -> list[tuple[str, dict, str]]:
    """Frozen (key, payload, context) triples a human grades into goldens.

    Payload and context are exactly what the future answers deepeval lane
    (#226) will hand its judge, so judge–human agreement compares grades of
    the same thing. Contexts are frozen at draft time: agreement stays
    comparable even as the corpus grows.
    """
    from bank.models import Question
    from evals.datasets.loaders import textbook_context_for_question
    from evals.golden import spread_indices

    artifact = load_artifact(record)
    answers: list[dict] = artifact.get("answers", [])
    items = []
    for idx in spread_indices(len(answers), sample):
        item = answers[idx]
        question = (
            Question.objects.filter(pk=int(item.get("id") or 0))
            .select_related("chapter")
            .first()
        )
        if question is None:
            continue
        items.append(
            (
                f"q:{question.pk}",
                _judge_payload(question, item),
                textbook_context_for_question(question),
            )
        )
    return items


def _judge_payload(question, item: dict) -> dict[str, Any]:
    """The answer-under-test as both the judge and a golden grader see it."""
    return {
        "question": question.text,
        "qtype": question.qtype,
        "marks": question.marks,
        "options": question.options,
        "generated_answer": item.get("answer", ""),
    }
