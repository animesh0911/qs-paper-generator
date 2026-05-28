"""SelectionEngine acceptance tests.

These tests verify that selection honours chapter weighting, the cognitive-mix
implied by the difficulty profile, and the no-duplicate / unfilled-reporting
contract called out in Slice 3.
"""
from __future__ import annotations

from collections import Counter

import pytest
from rest_framework import status

from bank.models import Chapter, CognitiveLevel, Question, QuestionType, Section
from papers.blueprint import PaperSpec, Slot
from papers.selection import (
    DIFFICULTY_PROFILES,
    CandidatePool,
    SelectionEngine,
    SelectionInput,
    SelectionReport,
)


def _spec(n_mcq: int) -> PaperSpec:
    return PaperSpec(
        name="mcq-only",
        slots=[Slot(Section.A, QuestionType.MCQ, 1) for _ in range(n_mcq)],
    )


def _make_question(*, chapter: Chapter | None, level: str, idx: int) -> Question:
    return Question.objects.create(
        section=Section.A,
        qtype=QuestionType.MCQ,
        marks=1,
        chapter=chapter,
        cognitive_level=level,
        text=f"Q-{chapter.slug if chapter else 'no'}-{level}-{idx}",
        options=[{"label": "A", "text": "a"}],
        answer="A",
    )


@pytest.fixture
def two_chapters(db):
    ch1 = Chapter.objects.get(slug="electricity")
    ch2 = Chapter.objects.get(slug="life-processes")
    return ch1, ch2


@pytest.fixture
def big_pool(two_chapters):
    """Populate ten questions per chapter and per cognitive level."""
    ch1, ch2 = two_chapters
    for chapter in (ch1, ch2):
        for level, _ in CognitiveLevel.choices:
            for i in range(10):
                _make_question(chapter=chapter, level=level, idx=i)
    return ch1, ch2


@pytest.mark.django_db
def test_selection_respects_chapter_weights_70_30(big_pool):
    """A 70/30 chapter weight on a 10-slot paper allocates 7/3 questions.

    Why this matters: the teacher's per-chapter weights are the primary lever
    for coverage; if the engine quietly ignores them the UI signal is a lie.
    """
    ch1, ch2 = big_pool
    spec = _spec(10)
    result = SelectionEngine().select(
        SelectionInput(
            spec=spec,
            chapter_slugs=[ch1.slug, ch2.slug],
            weights={ch1.slug: 0.7, ch2.slug: 0.3},
            difficulty="standard",
        )
    )
    counts = Counter()
    for qid in result.question_ids:
        assert qid is not None
        counts[Question.objects.get(id=qid).chapter.slug] += 1
    assert counts[ch1.slug] == 7
    assert counts[ch2.slug] == 3


@pytest.mark.django_db
def test_selection_meets_cognitive_mix_within_tolerance(big_pool):
    """Cognitive-level counts match the difficulty profile within ±1.

    Why ±1: largest-remainder allocation rounds quotas to integers, so the
    target can drift by at most one slot per cognitive bucket.
    """
    ch1, ch2 = big_pool
    n = 20
    spec = _spec(n)
    result = SelectionEngine().select(
        SelectionInput(
            spec=spec,
            chapter_slugs=[ch1.slug, ch2.slug],
            difficulty="standard",
        )
    )
    profile = DIFFICULTY_PROFILES["standard"]
    actual = Counter()
    for qid in result.question_ids:
        actual[Question.objects.get(id=qid).cognitive_level] += 1
    for level, ratio in profile.items():
        target = round(ratio * n)
        assert abs(actual[level] - target) <= 1, (level, actual[level], target)


@pytest.mark.django_db
def test_selection_no_in_paper_duplicates(big_pool):
    """Selected question ids are unique within a single paper.

    Why this matters: paying students should never see the same question
    twice in one paper, even if the bank pool is small.
    """
    ch1, _ = big_pool
    spec = _spec(15)
    result = SelectionEngine().select(
        SelectionInput(spec=spec, chapter_slugs=[ch1.slug])
    )
    filled = [q for q in result.question_ids if q is not None]
    assert len(filled) == len(set(filled))


@pytest.mark.django_db
def test_selection_reports_unfilled_on_insufficient_pool(two_chapters):
    """When the bank has fewer questions than slots, the gap is reported.

    Why best-effort + report (not raise): the teacher sees a partial paper
    plus an explicit list of which slots failed, so they can widen chapter
    selection rather than face an opaque error.
    """
    ch1, _ = two_chapters
    _make_question(chapter=ch1, level=CognitiveLevel.REMEMBER, idx=0)
    _make_question(chapter=ch1, level=CognitiveLevel.REMEMBER, idx=1)
    spec = _spec(5)
    result = SelectionEngine().select(
        SelectionInput(spec=spec, chapter_slugs=[ch1.slug])
    )
    assert sum(1 for q in result.question_ids if q is not None) == 2
    assert len(result.unfilled) == 3
    for entry in result.unfilled:
        assert entry["section"] == Section.A
        assert entry["qtype"] == QuestionType.MCQ
        assert entry["marks"] == 1
        assert "no candidate" in entry["reason"]


@pytest.mark.django_db
def test_assemble_persists_coverage_on_paper(api_client, big_pool):
    ch1, ch2 = big_pool
    # Seed enough non-MCQ questions too so the full board preset can be filled
    # by the assembler (selection runs across all buckets).
    for slot_section, qtype, marks in [
        (Section.B, QuestionType.VSA, 2),
        (Section.C, QuestionType.SA, 3),
        (Section.D, QuestionType.LA, 5),
        (Section.E, QuestionType.CASE, 4),
    ]:
        for chapter in (ch1, ch2):
            for i in range(20):
                Question.objects.create(
                    section=slot_section, qtype=qtype, marks=marks,
                    chapter=chapter, cognitive_level=CognitiveLevel.REMEMBER,
                    text=f"{qtype}-{chapter.slug}-{i}",
                )
    resp = api_client.post(
        "/api/papers/assemble",
        {
            "chapter_slugs": [ch1.slug, ch2.slug],
            "weights": {ch1.slug: 1, ch2.slug: 1},
            "difficulty": "standard",
        },
        format="json",
    )
    assert resp.status_code == status.HTTP_201_CREATED
    report = resp.data["report"]
    assert "coverage" in report
    assert "cog_coverage" in report
    assert "unfilled" in report
    # Both selected chapters appear in coverage.
    assert ch1.slug in report["coverage"]
    assert ch2.slug in report["coverage"]


# ---------------------------------------------------------------------------
# Pure-allocator tests: exercise _select_from_pool without touching the DB.
# These guard the algorithm independently of the ORM fetch step.
# ---------------------------------------------------------------------------


def test_pure_allocator_honours_chapter_weights_with_hand_built_pool():
    """Hand-built CandidatePool exercises allocation with no DB rows.

    Why this test exists: the algorithm should be reproducible from a pure
    in-memory pool. If a future refactor makes _select_from_pool reach into
    the ORM, this test fails immediately without any fixture cost.
    """
    bucket = (Section.A, QuestionType.MCQ, 1)
    pool: CandidatePool = {
        bucket: [
            (i, "electricity" if i < 50 else "life-processes", "R")
            for i in range(1, 101)
        ]
    }
    spec = PaperSpec(
        name="t", slots=[Slot(Section.A, QuestionType.MCQ, 1) for _ in range(10)]
    )
    inp = SelectionInput(
        spec=spec,
        chapter_slugs=["electricity", "life-processes"],
        weights={"electricity": 0.8, "life-processes": 0.2},
        difficulty="standard",
    )
    result = SelectionEngine._select_from_pool(inp, pool)
    coverage = result.coverage
    assert coverage["electricity"] == 8
    assert coverage["life-processes"] == 2


def test_selection_report_round_trips_through_dict():
    """to_dict()/from_dict() guards drift between engine output and storage.

    Why this test exists: the report shape is defined once in Python and
    must survive a JSON round-trip into Paper.report. A regression that
    drops a field or renames one fails here before it ships.
    """
    r = SelectionReport(
        coverage={"electricity": 2, "life-processes": 3},
        cog_coverage={"R": 2, "U": 3},
        unfilled=[{"slot_index": 0, "section": "A", "qtype": "MCQ", "marks": 1, "reason": "x"}],
    )
    assert SelectionReport.from_dict(r.to_dict()) == r


def test_pure_allocator_reports_unfilled_with_empty_pool():
    spec = PaperSpec(
        name="t", slots=[Slot(Section.A, QuestionType.MCQ, 1) for _ in range(3)]
    )
    inp = SelectionInput(spec=spec, chapter_slugs=["x"], difficulty="standard")
    result = SelectionEngine._select_from_pool(inp, {})
    assert result.question_ids == [None, None, None]
    assert len(result.unfilled) == 3


@pytest.mark.django_db
def test_assemble_rejects_unknown_difficulty(api_client, seeded_bank):
    resp = api_client.post(
        "/api/papers/assemble",
        {"difficulty": "nightmare"},
        format="json",
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
