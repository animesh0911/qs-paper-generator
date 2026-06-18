"""Tests for the bulk generated Question contract and validator."""

from __future__ import annotations

from ai_services.llm import ModelPurpose, resolve_chat_model_config
from bank.generation import (
    LangChainQuestionGenerator,
    QuestionGenerationRequest,
    build_question_generation_prompt,
    validate_generated_questions,
)


def _request() -> QuestionGenerationRequest:
    return QuestionGenerationRequest(
        chapter_slugs=("life-processes",),
        topic_names=("Nutrition",),
        count=1,
    )


def _question(**overrides):
    question = {
        "chapter_slug": "life-processes",
        "qtype": "mcq",
        "marks": 1,
        "cognitive_level": "R",
        "raw_text": "Which process releases energy from glucose?",
        "content": {
            "stem": [{"type": "paragraph", "text": "Which process releases energy?"}],
            "options": [
                {
                    "label": "A",
                    "content": [{"type": "paragraph", "text": "Respiration"}],
                },
                {"label": "B", "content": [{"type": "paragraph", "text": "Osmosis"}]},
                {"label": "C", "content": [{"type": "paragraph", "text": "Diffusion"}]},
                {"label": "D", "content": [{"type": "paragraph", "text": "Excretion"}]},
            ],
        },
        "topic_names": ["Nutrition"],
        "answer": "Respiration releases energy from glucose.",
        "source": {"type": "ai_generated", "name": "question-generation"},
    }
    question.update(overrides)
    return question


def test_validator_accepts_supported_question_types():
    """Generated candidates are canonical Question payloads before persistence."""
    payload = {
        "questions": [
            _question(qtype="mcq", marks=1),
            _question(qtype="very_short_answer", marks=2),
            _question(qtype="short_answer", marks=3),
            _question(qtype="long_answer", marks=5),
        ]
    }

    result = validate_generated_questions(payload, _request())

    assert len(result.valid_questions) == 4
    assert result.errors == ()


def test_validator_rejects_malformed_model_output():
    """Bad model shape is dropped before the future candidate lifecycle sees it."""
    result = validate_generated_questions({"questions": "not a list"}, _request())

    assert result.valid_questions == ()
    assert [error.code for error in result.errors] == ["missing_questions"]


def test_validator_reports_rejection_reasons():
    """Rejection reasons name the contract violation instead of hiding bad output."""
    payload = {
        "questions": [
            _question(
                qtype="case_based",
                marks=3,
                chapter_slug="invented",
                answer="",
                candidate_id="candidate-1",
            )
        ]
    }

    result = validate_generated_questions(payload, _request())

    assert result.valid_questions == ()
    assert {
        "workflow_field",
        "bad_qtype",
        "bad_chapter_slug",
        "empty_answer",
    } <= {error.code for error in result.errors}


def test_validator_rejects_bad_mcq_options():
    """MCQ consistency is deterministic: exactly four structured options."""
    payload = {
        "questions": [_question(content={"stem": [{"type": "paragraph", "text": "Q"}]})]
    }

    result = validate_generated_questions(payload, _request())

    assert result.valid_questions == ()
    assert "bad_mcq_options" in {error.code for error in result.errors}


def test_validator_rejects_mcq_answer_that_matches_no_option():
    """An MCQ answer must point back to one of the generated options."""
    payload = {"questions": [_question(answer="None of these generated options.")]}

    result = validate_generated_questions(payload, _request())

    assert result.valid_questions == ()
    assert "mcq_answer_mismatch" in {error.code for error in result.errors}


def test_prompt_keeps_workflow_fields_out_of_model_payload():
    """The prompt names Question data only; candidate lifecycle fields stay outside."""
    prompt = build_question_generation_prompt(_request())

    assert "candidate id" in prompt
    assert "batch id" in prompt
    assert "ai_generated" in prompt
    assert "approximately equally across selected Chapters" in prompt
    assert "mcq/1" in prompt
    assert "long_answer/5" in prompt


def test_question_generation_route_resolves_from_env(monkeypatch):
    """question_generation is a logical LiteLLM route, not a feature-code provider."""
    monkeypatch.setenv("LLM_QUESTION_GENERATION_PROVIDER", "openai")
    monkeypatch.setenv("LLM_QUESTION_GENERATION_MODEL", "gpt-test")

    config = resolve_chat_model_config(ModelPurpose.QUESTION_GENERATION)

    assert config.provider == "openai"
    assert config.model == "gpt-test"


def test_langchain_generator_uses_stubbed_model_without_network():
    """Generation can be verified with a fake model and no paid API call."""
    calls = []

    class _StructuredModel:
        def invoke(self, prompt):
            calls.append(prompt)
            return {"questions": [_question()]}

    class _Model:
        def with_structured_output(self, schema):
            calls.append(schema)
            return _StructuredModel()

    def make_model(purpose):
        calls.append(purpose)
        return _Model()

    result = LangChainQuestionGenerator(make_model=make_model).generate(_request())

    assert len(result) == 1
    assert calls[0] == ModelPurpose.QUESTION_GENERATION


def test_langchain_generator_drops_invalid_candidates_without_network():
    """Invalid model outputs are excluded before persistence, valid ones remain."""

    class _StructuredModel:
        def invoke(self, prompt):
            return {"questions": [_question(), _question(answer="")]}

    class _Model:
        def with_structured_output(self, schema):
            return _StructuredModel()

    result = LangChainQuestionGenerator(make_model=lambda purpose: _Model()).generate(
        _request()
    )

    assert len(result) == 1
    assert result[0]["answer"]
