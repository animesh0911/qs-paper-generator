"""Tests for the bulk generated Question contract and validator."""

from __future__ import annotations

from ai_services.llm import ModelPurpose, resolve_chat_model_config
from bank.citation_support import _tokens, review_candidate_citation_support
from bank.generated_question_gate import (
    validate_generated_questions as validate_with_gate,
)
from bank.generation import (
    QUESTION_GENERATION_RESPONSE_SCHEMA,
    LangChainQuestionGenerator,
    QuestionGenerationRequest,
    build_question_generation_prompt,
    node_question_targets,
    select_balanced_questions,
    validate_generated_questions,
)


def _two_topic_manifest() -> dict:
    return {
        "excerpts": [
            {
                "citation_id": "chunk-nutrition",
                "chapter_map_node_id": "node-nutrition",
                "text": "Nutrition supplies energy.",
            },
            {
                "citation_id": "chunk-respiration",
                "chapter_map_node_id": "node-respiration",
                "text": "Respiration releases energy from glucose.",
            },
        ],
    }


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
        "question_citation_ids": ["chunk-respiration"],
        "answer_citation_ids": ["chunk-respiration"],
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


def test_generated_question_gate_is_direct_test_surface():
    """GeneratedQuestionGate is the deterministic seam future batches call."""
    result = validate_with_gate({"questions": [_question()]}, _request())

    assert len(result.valid_questions) == 1
    assert result.errors == ()


def test_validator_rejects_malformed_model_output():
    """Bad model shape is dropped before the future candidate lifecycle sees it."""
    result = validate_generated_questions({"questions": "not a list"}, _request())

    assert result.valid_questions == ()
    assert [error.code for error in result.errors] == ["missing_questions"]


def test_validator_rejects_missing_model_output():
    """A missing structured-output envelope is a rejection, not a crash."""
    result = validate_generated_questions(None, _request())

    assert result.valid_questions == ()
    assert [error.code for error in result.errors] == ["malformed_payload"]


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


def test_validator_does_not_match_mcq_label_by_first_letter_only():
    """A prose answer starting with 'a' is not automatically option A."""
    payload = {"questions": [_question(answer="An unrelated answer starts with a.")]}

    result = validate_generated_questions(payload, _request())

    assert result.valid_questions == ()
    assert "mcq_answer_mismatch" in {error.code for error in result.errors}


def test_prompt_scales_default_question_type_distribution_to_requested_count():
    """Batch-size experiments must not ask for more typed questions than count."""
    prompt = build_question_generation_prompt(
        QuestionGenerationRequest(chapter_slugs=("carbon-and-its-compounds",), count=3)
    )

    distribution_line = prompt.split("Requested counts by QuestionType: ", 1)[1].split(
        "\n", 1
    )[0]

    assert "Total candidates: exactly 3" in prompt
    assert distribution_line == (
        "{'mcq': 1, 'very_short_answer': 1, 'short_answer': 1}"
    )
    assert "long_answer" not in distribution_line


def test_prompt_keeps_workflow_fields_out_of_model_payload():
    """The prompt names Question data only; candidate lifecycle fields stay outside."""
    prompt = build_question_generation_prompt(_request())

    assert "candidate id" in prompt
    assert "batch id" in prompt
    assert "ai_generated" in prompt
    assert "approximately equally across selected Chapters" in prompt
    assert "Requested counts by QuestionType" in prompt
    assert "raw_text must be a non-empty plain-text copy" in prompt
    assert "QuestionType/marks distribution" not in prompt
    assert "mcq/1" in prompt
    assert "long_answer/5" in prompt
    assert "Do not generate numerical" not in prompt
    assert "formula-only" not in prompt


def test_grounded_prompt_supplies_excerpts_and_requires_citations():
    """Grounded generation gets bounded NCERT context and citation rules."""
    request = QuestionGenerationRequest(
        chapter_slugs=("life-processes",),
        grounding_manifest={
            "unsupported_content_policy": "No formula-only chunks.",
            "excerpts": [
                {
                    "citation_id": "chunk-respiration",
                    "chapter_map_node_id": "node-nutrition",
                    "pages": [2],
                    "content_types": ["paragraph"],
                    "text": "Respiration releases energy from glucose.",
                }
            ],
        },
        count=1,
    )

    prompt = build_question_generation_prompt(request)

    assert "Use only the NCERT excerpts supplied below" in prompt
    assert "question_citation_ids" in prompt
    assert "answer_citation_ids" in prompt
    assert "[citation_id: chunk-respiration]" in prompt
    assert "Respiration releases energy from glucose." in prompt


def test_grounded_validator_rejects_unknown_citations():
    """Grounded candidates must cite supplied excerpt ids deterministically."""
    request = QuestionGenerationRequest(
        chapter_slugs=("life-processes",),
        grounding_manifest={"excerpts": [{"citation_id": "chunk-respiration"}]},
    )

    result = validate_generated_questions(
        {"questions": [_question(question_citation_ids=["invented"])]}, request
    )

    assert result.valid_questions == ()
    assert "unknown_citation" in {error.code for error in result.errors}


def test_citation_support_review_accepts_lexically_supported_candidate():
    """Semantic-support review records evidence beyond citation-id existence."""
    manifest = {
        "excerpts": [
            {
                "citation_id": "chunk-respiration",
                "text": "Respiration releases energy from glucose in cells.",
            }
        ]
    }

    review = review_candidate_citation_support(_question(), manifest)

    assert review.supported
    assert review.issues == ()


def test_citation_support_review_flags_unsupported_answer_claims():
    """A real citation id is not enough when cited text does not support answer."""
    manifest = {
        "excerpts": [
            {
                "citation_id": "chunk-respiration",
                "text": "Respiration releases energy from glucose in cells.",
            }
        ]
    }

    review = review_candidate_citation_support(
        _question(
            raw_text="What causes diamond to be hard?",
            content={
                "stem": [
                    {"type": "paragraph", "text": "What causes diamond to be hard?"}
                ]
            },
            answer=(
                "Diamond is hard because every carbon atom bonds to four other "
                "carbon atoms in a rigid three-dimensional network."
            ),
        ),
        manifest,
    )

    assert not review.supported
    assert "low_lexical_citation_overlap" in {issue.code for issue in review.issues}


def test_citation_support_review_flags_formula_or_diagram_heavy_questions():
    """MVP grounded generation keeps formula/diagram-heavy items in review."""
    manifest = {
        "excerpts": [
            {
                "citation_id": "chunk-respiration",
                "text": "Respiration releases energy from glucose in cells.",
            }
        ]
    }

    review = review_candidate_citation_support(
        _question(raw_text="Draw the electron-dot structure of ethene."), manifest
    )

    assert "formula_or_diagram_review_required" in {
        issue.code for issue in review.issues
    }


def test_citation_support_review_handles_numeric_and_unicode_tokens():
    """Citation review must not drop formulas, numerals, or non-English text."""
    candidate = _question(
        raw_text="कार्बन की संयोजकता कितनी है?",
        content={"stem": [{"type": "paragraph", "text": "कार्बन की संयोजकता कितनी है?"}]},
        answer="4",
    )
    manifest = {
        "excerpts": [
            {
                "citation_id": "chunk-respiration",
                "text": "कार्बन की संयोजकता 4 है।",
            }
        ]
    }

    review = review_candidate_citation_support(candidate, manifest)

    assert "कार्बन" in _tokens("कार्बन की संयोजकता")
    assert "संयोजकता" in _tokens("कार्बन की संयोजकता")
    assert review.supported


def test_node_question_targets_splits_evenly_with_remainder_to_earliest():
    """The total is split as evenly as possible; the remainder lands earliest."""
    targets = node_question_targets(("node-a", "node-b", "node-c"), 8)

    assert targets == {"node-a": 3, "node-b": 3, "node-c": 2}
    assert sum(targets.values()) == 8


def test_node_question_targets_is_empty_without_topic_nodes():
    """The chapter-only path keeps its old behaviour: no per-node allocation."""
    assert node_question_targets((), 10) == {}


def test_select_balanced_questions_trims_overage_to_per_node_target():
    """A node that over-delivers is trimmed back to its even target."""
    targets = {"node-nutrition": 1, "node-respiration": 1}
    nutrition = [
        _question(question_citation_ids=["chunk-nutrition"], raw_text=f"N{i}")
        for i in range(3)
    ]
    respiration = [
        _question(question_citation_ids=["chunk-respiration"], raw_text="R0")
    ]

    selected = select_balanced_questions(
        [*nutrition, *respiration], targets, _two_topic_manifest()
    )

    raw_texts = [question["raw_text"] for question in selected]
    assert raw_texts == ["N0", "R0"]


def test_select_balanced_questions_backfills_shortfall_from_surplus():
    """A node that under-delivers is backfilled from another node's surplus."""
    targets = {"node-nutrition": 1, "node-respiration": 1}
    nutrition = [
        _question(question_citation_ids=["chunk-nutrition"], raw_text=f"N{i}")
        for i in range(2)
    ]

    selected = select_balanced_questions(nutrition, targets, _two_topic_manifest())

    assert len(selected) == 2
    assert {question["raw_text"] for question in selected} == {"N0", "N1"}


def test_prompt_breaks_down_targets_per_topic_node_with_headroom():
    """Topic selection yields an explicit per-node breakdown plus review spare."""
    request = QuestionGenerationRequest(
        chapter_slugs=("life-processes",),
        chapter_map_node_ids=("node-nutrition", "node-respiration"),
        grounding_manifest=_two_topic_manifest(),
        count=4,
    )

    prompt = build_question_generation_prompt(request)

    assert "Per-topic question targets" in prompt
    assert "topic node node-nutrition: generate 3 candidates (final target 2)" in prompt
    assert (
        "topic node node-respiration: generate 3 candidates (final target 2)" in prompt
    )
    # Overshoot total drives the headline count (3 + 3), not the final 4.
    assert "Total candidates: exactly 6" in prompt


def test_generator_returns_evenly_distributed_candidates(monkeypatch):
    """End to end: the generator trims model output to the even per-node target."""
    request = QuestionGenerationRequest(
        chapter_slugs=("life-processes",),
        chapter_map_node_ids=("node-nutrition", "node-respiration"),
        grounding_manifest=_two_topic_manifest(),
        count=2,
    )
    model_output = {
        "questions": [
            _question(question_citation_ids=["chunk-nutrition"], raw_text="N0"),
            _question(question_citation_ids=["chunk-nutrition"], raw_text="N1"),
            _question(question_citation_ids=["chunk-respiration"], raw_text="R0"),
        ]
    }

    class _StructuredModel:
        def invoke(self, prompt):
            return model_output

    class _Model:
        def with_structured_output(self, schema):
            return _StructuredModel()

    result = LangChainQuestionGenerator(make_model=lambda purpose: _Model()).generate(
        request
    )

    raw_texts = sorted(question["raw_text"] for question in result)
    assert raw_texts == ["N0", "R0"]


def test_question_generation_route_resolves_from_env(monkeypatch):
    """question_generation is a logical LiteLLM route, not a feature-code provider."""
    monkeypatch.setenv("LLM_QUESTION_GENERATION_PROVIDER", "openai")
    monkeypatch.setenv("LLM_QUESTION_GENERATION_MODEL", "gpt-test")

    config = resolve_chat_model_config(ModelPurpose.QUESTION_GENERATION)

    assert config.provider == "openai"
    assert config.model == "gpt-test"


def test_question_generation_route_supports_deepseek_without_feature_sdk(monkeypatch):
    """DeepSeek is configured at the seam as an OpenAI-compatible provider."""
    monkeypatch.setenv("LLM_QUESTION_GENERATION_PROVIDER", "deepseek")
    monkeypatch.setenv("LLM_QUESTION_GENERATION_MODEL", "deepseek-test")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    config = resolve_chat_model_config(ModelPurpose.QUESTION_GENERATION)

    assert config.provider == "openai"
    assert config.model == "deepseek-test"
    assert config.init_kwargs["api_key"] == "test-key"
    assert config.init_kwargs["base_url"] == "https://api.deepseek.com"


def test_question_generation_route_allows_openai_compatible_gateway(monkeypatch):
    """OpenRouter/LiteLLM gateways stay server-side via provider base URL config."""
    monkeypatch.setenv("LLM_QUESTION_GENERATION_PROVIDER", "openai")
    monkeypatch.setenv("LLM_QUESTION_GENERATION_MODEL", "openrouter/test-model")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1")

    config = resolve_chat_model_config(ModelPurpose.QUESTION_GENERATION)

    assert config.provider == "openai"
    assert config.model == "openrouter/test-model"
    assert config.init_kwargs["api_key"] == "test-key"
    assert config.init_kwargs["base_url"] == "https://openrouter.ai/api/v1"


def test_question_generation_route_supports_openrouter_key(monkeypatch):
    """The checked-in OpenRouter secret file can be used without renaming keys."""
    monkeypatch.setenv("LLM_QUESTION_GENERATION_PROVIDER", "openrouter")
    monkeypatch.setenv("LLM_QUESTION_GENERATION_MODEL", "google/gemini-3.5-flash")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    config = resolve_chat_model_config(ModelPurpose.QUESTION_GENERATION)

    assert config.provider == "openai"
    assert config.model == "google/gemini-3.5-flash"
    assert config.init_kwargs["api_key"] == "test-key"
    assert config.init_kwargs["base_url"] == "https://openrouter.ai/api/v1"


def test_response_schema_is_openai_compatible_json_schema():
    """OpenAI-compatible gateways require a named JSON schema, not raw enums."""
    assert QUESTION_GENERATION_RESPONSE_SCHEMA["title"] == "QuestionGenerationResponse"
    assert QUESTION_GENERATION_RESPONSE_SCHEMA["description"]

    question_schema = QUESTION_GENERATION_RESPONSE_SCHEMA["properties"]["questions"]
    item_schema = question_schema["items"]
    qtype_enum = item_schema["properties"]["qtype"]["enum"]
    source_enum = item_schema["properties"]["source"]["properties"]["type"]["enum"]
    content_schema = item_schema["properties"]["content"]

    assert "question_citation_ids" in item_schema["required"]
    assert "answer_citation_ids" in item_schema["required"]
    assert item_schema["properties"]["raw_text"]["minLength"] == 1
    assert "stem" in content_schema["required"]
    assert content_schema["properties"]["stem"]["items"]["required"] == ["type", "text"]
    assert content_schema["properties"]["options"]["items"]["required"] == [
        "label",
        "content",
    ]
    assert qtype_enum == [
        "long_answer",
        "mcq",
        "short_answer",
        "very_short_answer",
    ]
    assert source_enum == ["ai_generated"]


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
