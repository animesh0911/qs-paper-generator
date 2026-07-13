"""Generation scenario: fixture node-id resolution + citation-scoped judging."""

import json
from dataclasses import dataclass, field

import pytest

from bank.models import Chapter
from corpus.chapter_map import ChapterMapBuilder
from corpus.models import ChapterMapNode, TextbookDocument, TextbookElement
from evals.judges.base import JudgeRequest, JudgeVerdict
from evals.scenarios import generation
from evals.scenarios.generation import _resolve_fixture

MANIFEST = {
    "excerpts": [
        {"citation_id": "c1", "text": "Carbon forms covalent bonds."},
        {"citation_id": "c2", "text": "Diamond is a giant covalent structure."},
        {"citation_id": "c3", "text": "Unrelated excerpt about light refraction."},
    ]
}


@dataclass
class FakeJudge:
    """Records every request it was asked to grade instead of calling an LLM."""

    judge_id: str = "fake"
    seen: list[JudgeRequest] = field(default_factory=list)

    def judge(self, request: JudgeRequest) -> JudgeVerdict:
        self.seen.append(request)
        return JudgeVerdict(
            scores={"ncert_fidelity": 5.0},
            judge_id=self.judge_id,
            rubric_version="v1",
        )


def _question(question_citation_ids=(), answer_citation_ids=()):
    return {
        "raw_text": "Why does carbon form covalent bonds?",
        "question_citation_ids": list(question_citation_ids),
        "answer_citation_ids": list(answer_citation_ids),
    }


def test_cited_context_scopes_to_question_and_answer_citation_ids():
    excerpt_text_by_id = generation._excerpt_text_by_id(MANIFEST)
    question = _question(question_citation_ids=["c1"], answer_citation_ids=["c2"])

    context = generation._cited_context(question, excerpt_text_by_id)

    assert "covalent bonds" in context
    assert "giant covalent structure" in context
    assert "light refraction" not in context


def test_cited_context_dedupes_and_ignores_unknown_ids():
    excerpt_text_by_id = generation._excerpt_text_by_id(MANIFEST)
    question = _question(
        question_citation_ids=["c1", "c1", "does-not-exist"],
        answer_citation_ids=["c1"],
    )

    context = generation._cited_context(question, excerpt_text_by_id)

    assert context == "Carbon forms covalent bonds."


def test_judge_sample_sends_only_cited_excerpts_to_the_judge():
    questions = [_question(question_citation_ids=["c1"], answer_citation_ids=["c2"])]
    judge = FakeJudge()

    generation._judge_sample(questions, MANIFEST, judge)

    [seen] = judge.seen
    assert "covalent bonds" in seen.context
    assert "light refraction" not in seen.context
    assert seen.context_kind == "ncert_excerpts"


def test_judge_sample_counts_questions_with_no_matching_citations():
    questions = [_question(), _question(question_citation_ids=["c1"])]
    judge = FakeJudge()

    result = generation._judge_sample(questions, MANIFEST, judge)

    assert result["n_uncited"] == 1
    assert result["n_judged"] == 2
    assert judge.seen[0].context == ""


def _artifact(tmp_path, questions):
    artifact_path = tmp_path / "run.json"
    artifact_path.write_text(
        json.dumps(
            {
                "questions": questions,
                "grounding_manifest": {
                    "excerpts": [
                        {"citation_id": "c1", "text": "Carbon forms bonds."},
                        {"citation_id": "c3", "text": "Unrelated excerpt."},
                    ]
                },
            }
        ),
        encoding="utf-8",
    )
    return artifact_path


def test_score_unit_scopes_judge_context_to_citations(tmp_path):
    artifact_path = _artifact(tmp_path, [_question(question_citation_ids=["c1"])])
    record = {"artifacts_path": str(artifact_path), "batch_size": 1}
    judge = FakeJudge()

    accuracy = generation.score_unit(record, judge)

    [seen] = judge.seen
    assert "Carbon forms bonds." in seen.context
    assert "Unrelated excerpt." not in seen.context
    assert accuracy["judge"]["n_uncited"] == 0
    assert accuracy["citation_support"]["n_reviewed"] == 1


def test_citation_support_reports_production_lexical_screen():
    manifest = {
        "excerpts": [
            {
                "citation_id": "c1",
                "text": "Carbon forms covalent bonds by sharing electrons "
                "between atoms.",
            }
        ]
    }
    supported = {
        "raw_text": "Why does carbon form covalent bonds?",
        "answer": "By sharing electrons between atoms.",
        "question_citation_ids": ["c1"],
        "answer_citation_ids": ["c1"],
    }
    uncited = {
        "raw_text": "What is Ohm's law?",
        "answer": "",
        "question_citation_ids": [],
        "answer_citation_ids": [],
    }

    support = generation._citation_support([supported, uncited], manifest)

    assert support["n_reviewed"] == 2
    assert support["question_supported_rate"] == 0.5
    assert support["answer_supported_rate"] == 0.5
    assert support["supported_rate"] == 0.5
    assert support["flags"]["missing_cited_text"] == 2


def test_golden_items_freeze_citation_scoped_context(tmp_path):
    artifact_path = _artifact(
        tmp_path,
        [_question(question_citation_ids=["c1"]), _question(), _question()],
    )
    record = {"artifacts_path": str(artifact_path), "scenario": "generation"}

    items = generation.golden_items(record, sample=2)

    assert [key for key, _, _ in items] == ["i:0", "i:1"]
    assert items[0][2] == "Carbon forms bonds."
    assert items[1][2] == ""


def test_score_unit_reports_judge_human_agreement_when_goldens_exist(
    tmp_path, monkeypatch
):
    from evals.golden import draft_golden_set

    monkeypatch.setattr("evals.golden.GOLDEN_DIR", tmp_path / "golden")
    artifact_path = _artifact(tmp_path, [_question(question_citation_ids=["c1"])])
    record = {
        "artifacts_path": str(artifact_path),
        "batch_size": 1,
        "scenario": "generation",
        "run_id": "r1",
    }
    golden_path = draft_golden_set(record, generation.golden_items(record, sample=1))
    raw = json.loads(golden_path.read_text(encoding="utf-8"))
    raw["items"][0]["human_scores"] = {"ncert_fidelity": 4}
    raw["verified_by"] = "animesh"
    raw["verified_at"] = "2026-07-10"
    golden_path.write_text(json.dumps(raw), encoding="utf-8")

    accuracy = generation.score_unit(record, FakeJudge())

    agreement = accuracy["judge_agreement"]
    assert agreement["n_judged"] == 1
    assert agreement["dimensions"]["ncert_fidelity"]["mean_abs_diff"] == 1.0


@pytest.fixture
def two_section_document(db):
    """A minimal chapter map: two sibling SECTION nodes in source order."""
    chapter = Chapter.objects.get(slug="carbon-and-its-compounds")
    document = TextbookDocument.objects.create(
        chapter=chapter,
        source_file_name="jesc104.pdf",
        source_hash="a" * 64,
        extractor_name="Docling",
        extractor_version="2.102.1",
        canonical_json_path="content/ncert/jesc104/jesc104.json",
        canonical_json_hash="b" * 64,
        page_count=1,
    )
    rows = [
        ("section_header", "4.1 First Topic", 1),
        ("text", "Some content under the first topic.", 1),
        ("section_header", "4.2 Second Topic", 1),
        ("text", "Some content under the second topic.", 1),
    ]
    for source_order, (element_type, text, page_number) in enumerate(rows):
        TextbookElement.objects.create(
            document=document,
            stable_element_id=f"element-{source_order}",
            element_type=element_type,
            source_order=source_order,
            page_number=page_number,
            bbox={"l": 1, "t": 2, "r": 3, "b": 0},
            text=text,
            structured_data={},
        )
    ChapterMapBuilder().rebuild(document)
    return chapter


@pytest.mark.django_db
def test_resolve_fixture_prefers_pinned_ids_over_the_runtime_selector(
    two_section_document,
):
    """A pinned id must win even when the selector would have picked another."""
    chapter = two_section_document
    second_section = ChapterMapNode.objects.get(
        document__chapter=chapter, title="4.2 Second Topic"
    )
    fixture = {
        "chapter_slug": chapter.slug,
        "chapter_map_node_ids": [second_section.stable_node_id],
        "node_selector": {"strategy": "first_major_topics", "count": 2},
    }

    resolved_chapter, node_ids = _resolve_fixture(fixture)

    assert resolved_chapter == chapter
    assert node_ids == (second_section.stable_node_id,)


@pytest.mark.django_db
def test_resolve_fixture_falls_back_to_selector_when_unpinned(two_section_document):
    """Without pinned ids, the documented runtime selector still applies."""
    chapter = two_section_document
    fixture = {
        "chapter_slug": chapter.slug,
        "chapter_map_node_ids": [],
        "node_selector": {"strategy": "first_major_topics", "count": 2},
    }

    _, node_ids = _resolve_fixture(fixture)

    assert len(node_ids) == 2
