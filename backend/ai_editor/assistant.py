"""Synchronous editor-assistant model calls: typed-intent routing and chat.

PRD #30 answers two editor surfaces inside the HTTP request (no async job):

* **intent** — classify a teacher's free-typed text into a route so the UI knows
  whether to chat, summarize, review, propose an edit, or refuse off-topic.
* **chat** — answer a paper/editor question read-only, without proposing any
  document change.

Both go through the shared model seam (``ai_services.llm.make_chat_model`` /
``ModelPurpose.EDITOR_ASSISTANT``) so provider choice and keys stay server-side.
``make_model`` is a module global so tests inject a ``GenericFakeChatModel`` and
never touch a provider or the network (Rule 13), the same way
``bank.management.commands.generate_answers`` is tested.

Where it fits:
- Called by: ``ai_editor.views.intent`` / ``ai_editor.views.chat``.
- Uses: ``ai_services.llm``.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import PydanticOutputParser, StrOutputParser
from pydantic import BaseModel, Field

from ai_services.llm import ModelPurpose, make_chat_model

logger = logging.getLogger(__name__)

# Routes the classifier may emit. ``off_topic`` is the polite refusal for
# requests that are not about the paper or the editor.
INTENT_ROUTES = ("chat", "summary", "review", "editor_edit", "off_topic")

# Few-shot anchors for the classifier — one per route — so routing is grounded
# in concrete teacher phrasing rather than zero-shot guesswork.
_INTENT_EXAMPLES = (
    '- "how many marks is section C" -> chat',
    '- "give me a quick overview of this paper" -> summary',
    '- "check the paper for coverage gaps and duplicates" -> review',
    "- \"change the section B heading to 'Short Answers'\" -> editor_edit",
    '- "what is the capital of France" -> off_topic',
)

# Injectable for tests (GenericFakeChatModel); production builds the real model.
make_model: Callable[[ModelPurpose], BaseChatModel] = make_chat_model

_GUARDRAIL = (
    "You are the assistant inside a CBSE Class 10 question-paper editor. You can "
    "explain, review, and suggest, but you can never rewrite sourced question "
    "text. Stay focused on the paper and the editor."
)


class IntentResult(BaseModel):
    """Classifier output: which editor route the typed text should take."""

    route: str = Field(description=f"One of: {', '.join(INTENT_ROUTES)}")
    reason: str = Field(description="One short sentence explaining the choice.")


def classify_intent(text: str, *, paper_title: str) -> dict:
    """Classify ``text`` into one of :data:`INTENT_ROUTES`.

    Returns ``{"route", "reason"}``. An unrecognised route is coerced to
    ``off_topic`` so a misbehaving model can never widen the routing surface.
    """
    parser = PydanticOutputParser(pydantic_object=IntentResult)
    examples = "\n".join(_INTENT_EXAMPLES)
    prompt = (
        f"{_GUARDRAIL}\n\n"
        f"Paper: {paper_title!r}.\n"
        f"Classify the teacher's request into exactly one route.\n"
        f"Examples:\n{examples}\n\n"
        f"{parser.get_format_instructions()}\n\n"
        f"Request: {text}"
    )
    try:
        result: IntentResult = (
            make_model(ModelPurpose.EDITOR_ASSISTANT) | parser
        ).invoke(prompt)
    except Exception as exc:  # noqa: BLE001 - provider/parser failures need safe UX
        logger.exception("Assistant intent classification failed: %s", exc)
        return {
            "route": "off_topic",
            "reason": "Fell back because the request could not be classified.",
        }
    route = result.route if result.route in INTENT_ROUTES else "off_topic"
    return {"route": route, "reason": result.reason}


def paper_snapshot(document: dict | None) -> str:
    """Compact factual summary of a paper document for grounding chat answers.

    Without this the chat model only sees the paper *title* and must guess at
    section structure or marks — the classic hallucination setup. A few lines of
    derived facts (sections, filled slots, marks) cost ~100 tokens and let the
    model answer "how many marks is Section C" from data instead of invention.
    Returns "" when there is no document; the prompt then says so explicitly.
    """
    if not isinstance(document, dict):
        return ""
    paper = document.get("paper")
    if not isinstance(paper, dict):
        return ""
    lines: list[str] = []
    total_marks = paper.get("totalMarks")
    duration = paper.get("durationMinutes")
    if total_marks is not None:
        lines.append(f"Total marks: {total_marks}.")
    if duration:
        lines.append(f"Duration: {duration} minutes.")
    for section in paper.get("sections", []):
        if not isinstance(section, dict):
            continue
        slots = [slot for slot in section.get("slots") or [] if isinstance(slot, dict)]
        filled = sum(1 for slot in slots if slot.get("selectedQuestionId"))
        or_groups = {
            slot.get("orGroup") for slot in slots if slot.get("orGroup") is not None
        }
        question_count = (
            len(slots) - sum(1 for s in slots if s.get("orGroup") is not None)
        ) + len(or_groups)
        title = section.get("title") or section.get("id") or "Section"
        subtitle = section.get("subtitle")
        label = f"{title} ({subtitle})" if subtitle else str(title)
        lines.append(
            f"{label}: {question_count} questions "
            f"({filled}/{len(slots)} slots filled), {section.get('marks')} marks."
        )
    return "\n".join(lines)


def answer_chat(text: str, *, paper_title: str, snapshot: str = "") -> str:
    """Answer a read-only paper/editor question. Never proposes a change."""
    facts = snapshot or "No structure facts are available for this paper."
    prompt = (
        f"{_GUARDRAIL}\n\n"
        f"Paper: {paper_title!r}.\n"
        f"Paper facts:\n{facts}\n\n"
        f"Answer the teacher's question concisely. Ground every number or "
        f"structural claim in the paper facts above; if the facts do not cover "
        f"it, say you cannot see that detail rather than guessing. Do not "
        f"propose document changes.\n\n"
        f"Question: {text}"
    )
    return (make_model(ModelPurpose.EDITOR_ASSISTANT) | StrOutputParser()).invoke(
        prompt
    )
