"""Pure answer-generation prompt/model contract tests (no database required)."""

from __future__ import annotations

import json

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from bank.answer_generation_core import (
    AnswerGenerator,
    AnswerQuestion,
    build_answer_prompt,
    render_answer_question,
)


def test_structured_question_regions_reach_answer_prompt():
    question = AnswerQuestion.from_mapping(
        {
            "id": 37,
            "qtype": "case_based",
            "marks": 4,
            "text": "Read the case and answer the questions.",
            "chapter_slug": "metals-and-non-metals",
            "content": {
                "stem": [{"type": "paragraph", "text": "Read the case."}],
                "passage": [{"type": "paragraph", "text": "Alloys are mixtures."}],
                "assertion": [{"type": "paragraph", "text": "Assertion text"}],
                "reason": [{"type": "paragraph", "text": "Reason text"}],
                "subparts": [
                    {
                        "label": "III",
                        "marks": 2,
                        "content": [
                            {"type": "equation", "text": "V = IR", "latex": "V=IR"},
                            {"type": "table", "rows": [["R", "3 Ω"]]},
                        ],
                    }
                ],
                "choices": [
                    {
                        "displayStyle": "or",
                        "chooseCount": 1,
                        "options": [
                            {
                                "label": "a",
                                "content": [{"type": "paragraph", "text": "Choice A"}],
                            }
                        ],
                    }
                ],
            },
        }
    )

    prompt = build_answer_prompt([question], "FORMAT")

    for expected in (
        "Alloys are mixtures.",
        "Assertion text",
        "Reason text",
        '"label":"III"',
        '"latex":"V=IR"',
        '"rows":[["R","3 Ω"]]',
        "Choice A",
        "answer exactly one alternative",
        "Do not include the unselected alternative",
        "Do not wrap the JSON in Markdown fences",
        "answer only what the supplied text supports",
    ):
        assert expected in prompt


def test_simple_question_avoids_duplicate_structured_stem_tokens():
    question = AnswerQuestion(
        id=1,
        qtype="short_answer",
        marks=3,
        chapter="Life Processes",
        text="Define photosynthesis.",
        content={"stem": [{"type": "paragraph", "text": "Define photosynthesis."}]},
    )

    block = render_answer_question(question)

    assert block.count("Define photosynthesis.") == 1
    assert "Structured content" not in block


def test_structured_prompt_prunes_empty_regions_and_duplicate_plain_stem():
    question = AnswerQuestion(
        id=2,
        qtype="case_based",
        marks=4,
        chapter="Electricity",
        text="Read the case.",
        content={
            "stem": [{"type": "paragraph", "text": "Read the case."}],
            "passage": [{"type": "paragraph", "text": "Useful case context."}],
            "options": [],
            "reason": None,
        },
    )

    block = render_answer_question(question)

    assert block.count("Read the case.") == 1
    assert '"stem"' not in block
    assert '"options"' not in block
    assert '"reason"' not in block
    assert "Useful case context." in block


def test_future_structured_regions_are_preserved_without_media_payloads():
    question = AnswerQuestion(
        id=2,
        qtype="short_answer",
        marks=3,
        chapter="Electricity",
        text="Name the component.",
        content={
            "stem": [{"type": "paragraph", "text": "Name the component."}],
            "assets": [
                {
                    "caption": "A resistor symbol",
                    "url": "https://private.example/large-image.png",
                }
            ],
        },
    )

    block = render_answer_question(question)

    assert "A resistor symbol" in block
    assert "private.example" not in block


def test_media_payload_is_removed_but_visual_description_survives():
    question = AnswerQuestion(
        id=2,
        qtype="short_answer",
        marks=3,
        chapter="Electricity",
        text="Study the circuit.",
        content={
            "stem": [
                {
                    "type": "image",
                    "text": "A series circuit with 3 Ω and 6 Ω resistors.",
                    "src": "data:image/png;base64,VERY_LARGE",
                    "assetId": "private-file",
                }
            ]
        },
    )

    block = render_answer_question(question)

    assert "series circuit" in block
    assert "VERY_LARGE" not in block
    assert "private-file" not in block


def test_artifact_generation_uses_exact_core_without_database():
    model = GenericFakeChatModel(
        messages=iter(
            [
                AIMessage(
                    content=json.dumps(
                        {
                            "answers": [
                                {"id": 8, "answer": "  Correct answer.  "},
                                {"id": 999, "answer": "Unexpected."},
                                {"id": 8, "answer": "Duplicate."},
                                {"id": 9, "answer": "   "},
                            ]
                        }
                    )
                )
            ]
        )
    )
    generator = AnswerGenerator(model)

    answers = generator.generate_mappings(
        [
            {
                "id": 8,
                "qtype": "mcq",
                "marks": 1,
                "rawText": "Which option is correct?",
                "options": [{"label": "A", "text": "The correct option"}],
            },
            {
                "id": 9,
                "qtype": "short_answer",
                "marks": 3,
                "rawText": "Blank answer?",
            },
            {
                "id": 10,
                "qtype": "short_answer",
                "marks": 3,
                "rawText": "Omitted answer?",
            },
        ]
    )

    assert answers.accepted == ({"id": 8, "answer": "Correct answer."},)
    assert answers.missing_ids == (9, 10)
    assert answers.duplicate_ids == (8,)
    assert answers.unexpected_ids == (999,)
    assert answers.blank_ids == (9,)
