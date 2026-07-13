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
    golden_agreement,
    load_artifact,
    new_record,
    save_artifact,
    settle_record,
    unit_wall,
)

SCENARIO = "generation"

# Per-call token priors for the budget gate, trued to the recorded smoke run
# (generation-20260710-134623): grounded calls carried ~14-17k prompt tokens
# (manifest + schema dominate) and ~700-900 output tokens per requested
# question across gemini/deepseek. The June 2026 cost report's 10.5k/170
# priors under-forecast that run ~3.5x.
_EST_INPUT_TOKENS = 15_000
_EST_OUTPUT_TOKENS_PER_QUESTION = 800


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

    Both fixtures (``datasets/fixtures/generation_requests.json``) carry
    pinned ``chapter_map_node_ids`` against the seeded corpus (issue #219), so
    ``_resolve_fixture`` below resolves them directly with no runtime-selector
    fallback. A live call still needs ``--yes`` (Rule 13) and a verified
    model in the registry.
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
            f"Chapter {fixture['chapter_slug']!r} not seeded — run "
            "seed_textbook_corpus (see evals/README.md's inputs checklist) "
            "or pin a different, already-seeded chapter_slug."
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
            "chapter map before running (see evals/README.md)."
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
    manifest: dict = artifact.get("grounding_manifest") or {}
    requested = int(record.get("batch_size") or 0)

    accuracy: dict[str, Any] = {
        "yield": len(questions) / requested if requested else 0.0,
        "qtype_mix": _qtype_mix(questions),
        "near_duplicate_rate": _near_duplicate_rate(questions),
        "citation_support": _citation_support(questions, manifest),
    }

    if judge is not None:
        accuracy["judge"] = _judge_sample(questions[:judge_sample], manifest, judge)
        accuracy.update(golden_agreement(record, judge))
    return accuracy


def golden_items(record: dict, sample: int) -> list[tuple[str, dict, str]]:
    """Frozen (key, payload, context) triples a human grades into goldens.

    Context is the same citation-scoped excerpt text ``_judge_sample`` hands
    the judge, so judge–human agreement compares grades of the same thing.
    """
    from evals.golden import spread_indices

    artifact = load_artifact(record)
    questions: list[dict] = artifact.get("questions", [])
    excerpt_text_by_id = _excerpt_text_by_id(artifact.get("grounding_manifest") or {})
    return [
        (
            f"i:{idx}",
            questions[idx],
            _cited_context(questions[idx], excerpt_text_by_id),
        )
        for idx in spread_indices(len(questions), sample)
    ]


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


def _citation_support(questions: list[dict], manifest: dict) -> dict[str, Any]:
    """Production's lexical citation screen, run over every stored candidate.

    ``bank.citation_support`` is the deterministic pre-review production
    applies before a human accepts a candidate; running it at score time gives
    a judge-independent grounding floor at zero API cost (it covers all
    candidates, not just the judged sample). Where it and the judge disagree —
    lexically unsupported but judged faithful, or the reverse — is exactly the
    sample worth human review when calibrating the judge.
    """
    from bank.citation_support import review_candidate_citation_support

    if not questions:
        return {"n_reviewed": 0}
    question_supported = answer_supported = fully_supported = 0
    flags: dict[str, int] = {}
    for question in questions:
        review = review_candidate_citation_support(question, manifest)
        question_supported += review.question_supported
        answer_supported += review.answer_supported
        fully_supported += review.supported
        for issue in review.issues:
            flags[issue.code] = flags.get(issue.code, 0) + 1
    return {
        "n_reviewed": len(questions),
        "question_supported_rate": question_supported / len(questions),
        "answer_supported_rate": answer_supported / len(questions),
        "supported_rate": fully_supported / len(questions),
        "flags": flags,
    }


def _judge_sample(
    questions: list[dict], manifest: dict, judge: Judge
) -> dict[str, Any]:
    """Judge each sampled question against only the excerpts it cites.

    ``question_citation_ids``/``answer_citation_ids`` are required output
    fields (``bank.generation``'s schema); scoping context to the excerpts a
    candidate actually names — instead of the whole grounding manifest — is
    what makes ``ncert_fidelity``/``answer_correctness`` a check against what
    the model claimed to use, not everything it could have used.
    """
    excerpt_text_by_id = _excerpt_text_by_id(manifest)
    contexts = [_cited_context(question, excerpt_text_by_id) for question in questions]
    verdicts = [
        judge.judge(
            JudgeRequest(
                rubric_name="generation",
                payload=question,
                context=context,
                context_kind="ncert_excerpts",
            )
        )
        for question, context in zip(questions, contexts)
    ]
    summary = summarise_verdicts(verdicts)
    summary["n_uncited"] = sum(1 for context in contexts if not context)
    return summary


def _excerpt_text_by_id(manifest: dict) -> dict[str, str]:
    return {
        excerpt["citation_id"]: str(excerpt.get("text", ""))
        for excerpt in manifest.get("excerpts", [])
        if isinstance(excerpt, dict) and isinstance(excerpt.get("citation_id"), str)
    }


def _cited_context(question: dict, excerpt_text_by_id: dict[str, str]) -> str:
    """The subset of manifest excerpts this candidate's citations point to."""
    citation_ids = dict.fromkeys(
        [
            *_citation_ids(question.get("question_citation_ids")),
            *_citation_ids(question.get("answer_citation_ids")),
        ]
    )
    texts = (
        excerpt_text_by_id[citation_id]
        for citation_id in citation_ids
        if citation_id in excerpt_text_by_id
    )
    return "\n\n".join(text for text in texts if text)


def _citation_ids(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


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
