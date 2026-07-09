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
- accuracy → textbook-grounded judging (the user-chosen ground truth): NCERT
  excerpts retrieved per question through the production corpus retriever;
  the ``answers`` rubric scores correctness/groundedness/marks-depth, and
  runs record corpus *coverage* so ungrounded verdicts are reported apart.
"""

from __future__ import annotations

import argparse
from math import ceil
from typing import Any

from evals.budget import UnitEstimate
from evals.judges.base import Judge, JudgeRequest
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
    """Chunked production answer generation over one upload's questions.

    PLACEHOLDER (issue: "answers eval — question seeding"): the run needs
    Question rows. v1 requires ``--ingestion-job`` pointing at a completed
    extraction in the eval database. The issue adds a seeding path that loads
    a stored extraction artifact through ``Ingestor.ingest_extracted`` (the
    production persist tail) under a dedicated eval school/user, so answer
    runs are reproducible without re-running paid extraction.
    """
    from bank.answer_generation import USABLE_PARSE_QUALITIES, BankAnswerGenerator
    from bank.models import IngestionJob

    spec = get_model(unit.model_eval_id)
    record = new_record(unit, spec)
    meter = Meter(spec.model)

    job_id = unit.config.get("ingestion_job_id")
    if not job_id:
        raise EvalNotImplemented(
            "Pass --ingestion-job <id> (a completed extraction) until the "
            "artifact-seeding path lands (issue: answers eval)."
        )
    job = IngestionJob.objects.get(pk=job_id)
    question_ids = list(
        job.questions.filter(parse_quality__in=USABLE_PARSE_QUALITIES)
        .order_by("section", "id")
        .values_list("pk", flat=True)
    )
    limit = int(unit.config.get("question_limit") or 0)
    if limit:
        question_ids = question_ids[:limit]
    if not question_ids:
        raise EvalNotImplemented(
            f"IngestionJob {job_id} has no usable questions; extract first."
        )

    chunk_size = int(unit.config["chunk_size"])
    record.batch_size = len(question_ids)
    answers: list[dict] = []

    with unit_wall(record):
        with seam_env(spec.env_overrides("answer_generation")):
            generator = BankAnswerGenerator(make_model=metered_make_model(meter))
            for start in range(0, len(question_ids), chunk_size):
                answers.extend(
                    generator.generate(question_ids[start : start + chunk_size])
                )

    record.delivered = len(answers)
    save_artifact(
        record,
        {
            "ingestion_job_id": job_id,
            "question_ids": question_ids,
            "chunk_size": chunk_size,
            "answers": answers,
        },
    )
    record.success = True
    return settle_record(record, meter, spec)


# ---------------------------------------------------------------------------
# Scoring phase
# ---------------------------------------------------------------------------


def score_unit(
    record: dict, judge: Judge | None, *, judge_sample: int = 12
) -> dict[str, Any]:
    """Coverage + textbook-grounded judged accuracy for one stored run."""
    from bank.models import Question
    from evals.datasets.loaders import corpus_coverage, textbook_context_for_question
    from evals.scenarios.generation import summarise_verdicts

    artifact = load_artifact(record)
    answers: list[dict] = artifact.get("answers", [])
    question_ids = [int(item["id"]) for item in answers if item.get("id")]
    questions = {
        q.pk: q
        for q in Question.objects.filter(pk__in=question_ids).select_related("chapter")
    }

    accuracy: dict[str, Any] = {
        "answered_rate": (
            len(answers) / record.get("batch_size", 1)
            if record.get("batch_size")
            else 0.0
        ),
        "corpus_coverage": corpus_coverage(
            [q.chapter.slug for q in questions.values() if q.chapter]
        ).fraction,
    }

    if judge is not None:
        verdicts = []
        for item in answers[:judge_sample]:
            question = questions.get(int(item.get("id", 0)))
            if question is None:
                continue
            context = textbook_context_for_question(question)
            verdicts.append(
                judge.judge(
                    JudgeRequest(
                        rubric_name="answers",
                        payload={
                            "question": question.text,
                            "qtype": question.qtype,
                            "marks": question.marks,
                            "options": question.options,
                            "generated_answer": item.get("answer", ""),
                        },
                        context=context,
                        context_kind="ncert_excerpts" if context else "",
                    )
                )
            )
        accuracy["judge"] = summarise_verdicts(verdicts)

    # PLACEHOLDER (issue: "answers eval — golden calibration"): compare judge
    # verdicts against the hand-verified golden set in /content/eval/golden/
    # and report judge–human agreement alongside the scores.
    return accuracy
