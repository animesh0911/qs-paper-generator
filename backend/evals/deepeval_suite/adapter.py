"""Stored run artifacts → deepeval test cases (generation scenario).

The adapter renders each generated question the way a grader reads it (stem,
options, answer) and scopes ``retrieval_context`` to the excerpts the
candidate actually cites — the same citation-scoping decision the seam judge
uses, so deepeval metrics measure the citation contract, not everything the
model could have seen. The raw payload and manifest ride along in
``metadata`` for the pure-code metrics.
"""

from __future__ import annotations

from typing import Any

from deepeval.test_case import LLMTestCase

from evals.scenarios.base import load_artifact


def generation_test_cases(
    record: dict[str, Any], indices: list[int] | None = None
) -> list[LLMTestCase]:
    """Build one test case per (selected) question of one stored run."""
    artifact = load_artifact(record)
    questions: list[dict] = artifact.get("questions", [])
    manifest: dict = artifact.get("grounding_manifest") or {}
    excerpts = [
        excerpt
        for excerpt in manifest.get("excerpts", [])
        if isinstance(excerpt, dict) and isinstance(excerpt.get("citation_id"), str)
    ]
    text_by_id = {e["citation_id"]: str(e.get("text", "")) for e in excerpts}
    all_texts = [text for text in text_by_id.values() if text]
    fixture = artifact.get("request_fixture") or {}
    task = (
        f"Generate {record.get('batch_size')} CBSE Class 10 Science exam "
        f"questions grounded in NCERT chapter "
        f"{fixture.get('chapter_slug', '?')!r}, citing the supplied excerpts."
    )

    if indices is None:
        indices = list(range(len(questions)))
    cases = []
    for idx in indices:
        if not 0 <= idx < len(questions):
            continue
        question = questions[idx]
        cited = _cited_texts(question, text_by_id)
        cases.append(
            LLMTestCase(
                name=f"{record.get('run_id', 'run')}:i{idx}",
                input=task,
                actual_output=render_question(question),
                retrieval_context=cited or None,
                context=all_texts or None,
                metadata={
                    "run_id": record.get("run_id"),
                    "model_eval_id": record.get("model_eval_id"),
                    "batch_size": record.get("batch_size"),
                    "question_index": idx,
                    "payload": question,
                    "manifest_excerpts": excerpts,
                },
            )
        )
    return cases


def render_question(payload: dict[str, Any]) -> str:
    """One generated candidate as the text a grader (or judge) reads."""
    lines = [
        f"[{payload.get('qtype', '?')} · {payload.get('marks', '?')} mark(s)]",
        str(payload.get("raw_text") or _stem_text(payload) or "").strip(),
    ]
    for option in (payload.get("content") or {}).get("options") or []:
        label = option.get("label", "?")
        text = " ".join(
            block.get("text", "")
            for block in option.get("content") or []
            if isinstance(block, dict)
        ).strip()
        lines.append(f"({label}) {text}")
    lines.append(f"Answer: {payload.get('answer', '')}")
    return "\n".join(line for line in lines if line)


def _stem_text(payload: dict[str, Any]) -> str:
    blocks = (payload.get("content") or {}).get("stem") or []
    return " ".join(
        block.get("text", "") for block in blocks if isinstance(block, dict)
    ).strip()


def _cited_texts(question: dict, text_by_id: dict[str, str]) -> list[str]:
    citation_ids = dict.fromkeys(
        [
            *_ids(question.get("question_citation_ids")),
            *_ids(question.get("answer_citation_ids")),
        ]
    )
    return [
        text_by_id[citation_id]
        for citation_id in citation_ids
        if text_by_id.get(citation_id)
    ]


def _ids(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]
