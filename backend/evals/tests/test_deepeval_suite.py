"""deepeval suite: adapter mapping, code metrics, schema coercion — offline."""

import json

import pytest
from pydantic import BaseModel

from evals.deepeval_suite import coerce_schema, generation_test_cases, render_question
from evals.deepeval_suite.metrics import CitationSupportMetric, QuestionShapeMetric

MCQ = {
    "qtype": "mcq",
    "marks": 1,
    "raw_text": "Why does carbon form covalent bonds?",
    "content": {
        "stem": [{"type": "paragraph", "text": "Why does carbon form bonds?"}],
        "options": [
            {"label": "A", "content": [{"type": "paragraph", "text": "Sharing"}]},
            {"label": "B", "content": [{"type": "paragraph", "text": "Transfer"}]},
            {"label": "C", "content": [{"type": "paragraph", "text": "Ions"}]},
            {"label": "D", "content": [{"type": "paragraph", "text": "Metals"}]},
        ],
    },
    "answer": "A",
    "question_citation_ids": ["c1"],
    "answer_citation_ids": ["c1"],
}


def _record(tmp_path, questions):
    artifact_path = tmp_path / "run.json"
    artifact_path.write_text(
        json.dumps(
            {
                "request_fixture": {"chapter_slug": "carbon-and-its-compounds"},
                "grounding_manifest": {
                    "excerpts": [
                        {"citation_id": "c1", "text": "Carbon shares electrons."},
                        {"citation_id": "c2", "text": "Unrelated excerpt."},
                    ]
                },
                "questions": questions,
            }
        ),
        encoding="utf-8",
    )
    return {
        "run_id": "r1",
        "model_eval_id": "m",
        "batch_size": len(questions),
        "artifacts_path": str(artifact_path),
        "scenario": "generation",
    }


def test_render_question_reads_like_an_exam_item():
    text = render_question(MCQ)

    assert "[mcq · 1 mark(s)]" in text
    assert "Why does carbon form covalent bonds?" in text
    assert "(A) Sharing" in text
    assert text.endswith("Answer: A")


def test_generation_test_cases_scope_retrieval_context_to_citations(tmp_path):
    record = _record(tmp_path, [MCQ])

    [case] = generation_test_cases(record)

    assert case.name == "r1:i0"
    assert case.retrieval_context == ["Carbon shares electrons."]
    assert set(case.context) == {"Carbon shares electrons.", "Unrelated excerpt."}
    assert case.metadata["payload"] == MCQ
    assert case.metadata["question_index"] == 0


def test_generation_test_cases_select_indices(tmp_path):
    record = _record(tmp_path, [MCQ, dict(MCQ, raw_text="Second?")])

    cases = generation_test_cases(record, indices=[1])

    assert [c.name for c in cases] == ["r1:i1"]
    uncited = dict(MCQ, question_citation_ids=[], answer_citation_ids=[])
    [case] = generation_test_cases(_record(tmp_path, [uncited]))
    assert case.retrieval_context is None


def test_question_shape_metric_passes_a_clean_mcq(tmp_path):
    record = _record(tmp_path, [MCQ])
    [case] = generation_test_cases(record)
    metric = QuestionShapeMetric()

    score = metric.measure(case)

    assert score == 1.0
    assert metric.is_successful()


def test_question_shape_metric_names_each_failure(tmp_path):
    broken = dict(
        MCQ,
        marks=3,
        answer="E",
        question_citation_ids=[],
    )
    record = _record(tmp_path, [broken])
    [case] = generation_test_cases(record)
    metric = QuestionShapeMetric()

    score = metric.measure(case)

    assert score < 1.0
    assert not metric.is_successful()
    assert "marks" in metric.reason
    assert "not a label" in metric.reason
    assert "question_citation_ids empty" in metric.reason


def test_citation_support_metric_mirrors_production_screen(tmp_path):
    supported = dict(
        MCQ,
        raw_text="Why does carbon share electrons?",
        answer="Carbon shares electrons.",
    )
    record = _record(tmp_path, [supported])
    [case] = generation_test_cases(record)
    metric = CitationSupportMetric()

    metric.measure(case)

    assert "lexically supported" in metric.reason or metric.score < 1.0

    uncited = dict(MCQ, question_citation_ids=[], answer_citation_ids=[])
    [case] = generation_test_cases(_record(tmp_path, [uncited]))
    score = metric.measure(case)
    assert score < 1.0
    assert "missing_cited_text" in metric.reason


class _Verdict(BaseModel):
    score: float
    reason: str


def test_coerce_schema_parses_json_out_of_noise():
    raw = 'Grading done.\n{"score": 0.8, "reason": "solid"}\nBye.'

    verdict = coerce_schema(raw, _Verdict)

    assert verdict.score == 0.8
    assert verdict.reason == "solid"


def test_coerce_schema_returns_text_without_schema_and_raises_on_garbage():
    assert coerce_schema("plain text") == "plain text"
    with pytest.raises(ValueError, match="_Verdict"):
        coerce_schema("no json here", _Verdict)
