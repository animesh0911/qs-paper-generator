"""Scenario 1 — bulk question generation.

Production path under test: ``bank.generation.LangChainQuestionGenerator``
(the exact object the generation graph's ``generate`` node calls), grounded by
the production corpus assembler (``bank.generation_batches.
build_context_assembler``). Model routing rides ``LLM_QUESTION_GENERATION_*``
env overrides — the same knobs a deploy would set.

Brief mapping:
- batch_size (30/15; larger = premium candidate) → ``QuestionGenerationRequest
  .count``; it is the primary output-token driver.
- outputs per run → cost (metered tokens × registry rates), latency (per-call
  + unit wall), batch_size requested vs delivered, accuracy (below).
- accuracy → deterministic: delivered/requested yield, qtype-mix conformance,
  near-duplicate rate; judge (NCERT-grounded, rubric ``generation``): fidelity,
  self-containedness, qtype conformity, answer correctness.

Note on yield: ``LangChainQuestionGenerator.generate`` validates and trims
internally, so raw-model candidate counts are not observable from the outside.
delivered/requested is the honest end-to-end yield; per-candidate validation
telemetry would need a production hook (deliberately out of scope).
"""

from __future__ import annotations

import argparse
import hashlib
import re
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

SCENARIO = "generation"

# Rough per-call token priors for the budget gate, from the June 2026 cost
# report's representative Q&A call (10.5k in / 5k out at batch 30). Output
# scales ~linearly with batch size; input is dominated by grounding + schema.
_EST_INPUT_TOKENS = 10_500
_EST_OUTPUT_TOKENS_PER_QUESTION = 170  # ≈5k out / 30 questions


def build_units(args: argparse.Namespace) -> list[EvalUnit]:
    from evals.datasets.loaders import load_generation_fixtures

    fixtures = load_generation_fixtures()
    wanted = set(args.fixtures) if getattr(args, "fixtures", None) else None
    units = []
    for fixture in fixtures:
        if wanted and fixture["fixture_id"] not in wanted:
            continue
        for model_id in args.models:
            for batch_size in args.batch_sizes:
                for trial in range(args.trials):
                    units.append(
                        EvalUnit(
                            scenario=SCENARIO,
                            arm="grounded",
                            model_eval_id=model_id,
                            config={
                                "fixture_id": fixture["fixture_id"],
                                "batch_size": batch_size,
                            },
                            trial=trial,
                        )
                    )
    return units


def estimate(unit: EvalUnit) -> UnitEstimate:
    batch = int(unit.config["batch_size"])
    return UnitEstimate(
        label=unit.label,
        calls=1,  # the single paid call per batch (Rule 13)
        input_tokens_per_call=_EST_INPUT_TOKENS,
        output_tokens_per_call=_EST_OUTPUT_TOKENS_PER_QUESTION * batch,
    )


# ---------------------------------------------------------------------------
# Paid phase
# ---------------------------------------------------------------------------


def run_unit(unit: EvalUnit) -> RunRecord:
    """One production generation call, metered.

    PLACEHOLDER (issue: "generation eval — fixtures & run"): the wiring below
    is the real production path, but it can only execute once
    - the corpus is seeded for the fixture chapters (``seed_textbook_corpus``
      + chapter-map import for all fixture chapters), and
    - fixtures resolve to real ``ChapterMapNode.stable_node_id`` values
      (``_resolve_node_ids`` below implements the runtime selector; the issue
      pins explicit ids once the seed is final).
    """
    from bank.generation import (
        DIFFICULTY_TARGETS_BY_PRESET,
        LangChainQuestionGenerator,
        QuestionGenerationRequest,
    )
    from bank.generation_batches import build_context_assembler
    from corpus.retrieval import TextbookRetrievalRequest
    from evals.datasets.loaders import load_generation_fixtures

    spec = get_model(unit.model_eval_id)
    record = new_record(unit, spec)
    record.batch_size = int(unit.config["batch_size"])
    meter = Meter(spec.model)

    fixture = next(
        f
        for f in load_generation_fixtures()
        if f["fixture_id"] == unit.config["fixture_id"]
    )
    chapter, node_ids = _resolve_fixture(fixture)

    with unit_wall(record):
        context = build_context_assembler().retrieve(
            TextbookRetrievalRequest(chapter=chapter, chapter_map_node_ids=node_ids)
        )
        manifest = context.to_generation_manifest()
        request = QuestionGenerationRequest(
            chapter_slugs=(fixture["chapter_slug"],),
            chapter_map_node_ids=node_ids,
            topic_names=tuple(fixture.get("topic_names") or ()),
            difficulty_targets=DIFFICULTY_TARGETS_BY_PRESET.get(
                fixture.get("difficulty_preset", "balanced")
            ),
            grounding_manifest=manifest,
            count=record.batch_size,
        )
        with seam_env(spec.env_overrides("question_generation")):
            generator = LangChainQuestionGenerator(make_model=metered_make_model(meter))
            payloads = generator.generate(request)

    record.delivered = len(payloads)
    save_artifact(
        record,
        {
            "request_fixture": fixture,
            "grounding_manifest": manifest,
            "questions": payloads,
        },
    )
    record.success = True
    return settle_record(record, meter, spec)


def _resolve_fixture(fixture: dict):
    """Fixture → (Chapter, node_ids), resolving the runtime node selector."""
    from bank.models import Chapter
    from corpus.models import ChapterMapNode

    chapter = Chapter.objects.filter(slug=fixture["chapter_slug"]).first()
    if chapter is None:
        raise EvalNotImplemented(
            f"Chapter {fixture['chapter_slug']!r} not seeded — run the corpus "
            "seed commands first (issue: generation eval — fixtures & run)."
        )
    node_ids = tuple(fixture.get("chapter_map_node_ids") or ())
    if not node_ids:
        selector = fixture.get("node_selector") or {}
        count = int(selector.get("count", 2))
        node_ids = tuple(
            ChapterMapNode.objects.filter(document__chapter=chapter)
            .order_by("source_start", "stable_node_id")
            .values_list("stable_node_id", flat=True)[:count]
        )
    if not node_ids:
        raise EvalNotImplemented(
            f"No ChapterMapNodes for {fixture['chapter_slug']!r}; import the "
            "chapter map before running (issue: generation eval)."
        )
    return chapter, node_ids


# ---------------------------------------------------------------------------
# Scoring phase
# ---------------------------------------------------------------------------


def score_unit(
    record: dict, judge: Judge | None, *, judge_sample: int = 10
) -> dict[str, Any]:
    """Deterministic quality metrics + judged accuracy for one stored run."""
    artifact = load_artifact(record)
    questions: list[dict] = artifact.get("questions", [])
    requested = int(record.get("batch_size") or 0)

    accuracy: dict[str, Any] = {
        "yield": len(questions) / requested if requested else 0.0,
        "qtype_mix": _qtype_mix(questions),
        "near_duplicate_rate": _near_duplicate_rate(questions),
    }

    if judge is not None:
        accuracy["judge"] = _judge_sample(
            questions[:judge_sample], artifact.get("grounding_manifest") or {}, judge
        )
    return accuracy


def _qtype_mix(questions: list[dict]) -> dict[str, int]:
    mix: dict[str, int] = {}
    for question in questions:
        qtype = str(question.get("qtype", "unknown"))
        mix[qtype] = mix.get(qtype, 0) + 1
    return mix


def _near_duplicate_rate(questions: list[dict]) -> float:
    """Share of questions whose normalised stem collides with an earlier one."""
    if not questions:
        return 0.0
    seen: set[str] = set()
    dupes = 0
    for question in questions:
        text = re.sub(r"\W+", " ", str(question.get("raw_text", ""))).lower().strip()
        digest = hashlib.md5(text.encode()).hexdigest()
        if digest in seen:
            dupes += 1
        seen.add(digest)
    return dupes / len(questions)


def _judge_sample(
    questions: list[dict], manifest: dict, judge: Judge
) -> dict[str, Any]:
    """Judge each sampled question against the excerpts it was grounded on.

    PLACEHOLDER (issue: "generation eval — judge scoring"): context below is
    the full manifest excerpt text; the issue should narrow it to the excerpts
    the question actually cites (question_citation_ids) and calibrate the
    rubric on a hand-reviewed sample.
    """
    context = "\n\n".join(
        str(excerpt.get("text", "")) for excerpt in manifest.get("excerpts", [])
    )
    verdicts = [
        judge.judge(
            JudgeRequest(
                rubric_name="generation",
                payload=question,
                context=context,
                context_kind="ncert_excerpts",
            )
        )
        for question in questions
    ]
    return summarise_verdicts(verdicts)


def summarise_verdicts(verdicts) -> dict[str, Any]:
    """Aggregate judge verdicts: mean per dimension + flag counts + failures."""
    ok = [v for v in verdicts if v.ok]
    dims: dict[str, list[float]] = {}
    flags: dict[str, int] = {}
    for verdict in ok:
        for dim, value in verdict.scores.items():
            if value >= 0:  # -1 = rubric's "not applicable" sentinel
                dims.setdefault(dim, []).append(value)
        for flag in verdict.flags:
            flags[flag] = flags.get(flag, 0) + 1
    return {
        "n_judged": len(ok),
        "n_failed": len(verdicts) - len(ok),
        "mean_scores": {d: sum(v) / len(v) for d, v in dims.items() if v},
        "flags": flags,
        "rubric_version": ok[0].rubric_version if ok else "",
        "judge_id": ok[0].judge_id if ok else "",
    }
