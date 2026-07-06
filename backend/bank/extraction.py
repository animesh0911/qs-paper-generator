"""Question extraction adapters for CBSE paper ingestion.

This module owns the Extractor seam: provider schemas/prompts, PDF page slicing,
per-page model calls, payload coercion, de-duplication, and page-number rewrite.
The Ingestor module consumes already-extracted Question payloads and owns the
persistence tail.
"""

from __future__ import annotations

import copy
import hashlib
import re
from collections.abc import Callable, Iterable
from typing import Protocol

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage

from ai_services.llm import LLMClient, ModelPurpose, make_chat_model, make_llm_client

from . import content as content_mod
from .extraction_pdf import count_pages, slice_page, split_pages
from .extraction_pdf import split_pages_for_runtime as _split_pages_for_runtime
from .extraction_prompt import page_prompt as _page_prompt
from .models import Chapter, CognitiveLevel

# Numerical: equation-like text, SI units, or standalone numbers with units.
_NUMERICAL_RE = re.compile(
    r"""
    \d+\.?\d*\s*(?:m/s|kg|mol|J|W|N|Pa|°C|K|A|V|Ω|Hz|m|cm|nm|km|g|mg|L|mL)\b
    | =\s*[-+]?\d
    | \b\d{1,3}\s*[×x]\s*10\^?\d
    """,
    re.VERBOSE | re.IGNORECASE,
)
_DIAGRAM_RE = re.compile(r"\bfig(?:ure)?\.?\s*\d*\b|\bdiagram\b", re.IGNORECASE)

# Per-page extraction derives the section deterministically from each question's
# marks (Rule 5 — code, not the model, owns this mapping). In the CBSE Cl.10
# Science format the mark value is a clean key to the section: A=1, B=2, C=3,
# E=4 (case-based), D=5 (long answer). When the model omits a usable mark, the
# qtype implies one.
MARKS_TO_SECTION: dict[int, str] = {1: "A", 2: "B", 3: "C", 4: "E", 5: "D"}
QTYPE_DEFAULT_MARKS: dict[str, int] = {
    "mcq": 1,
    "assertion_reason": 1,
    "very_short_answer": 2,
    "short_answer": 3,
    "long_answer": 5,
    "case_based": 4,
    # Legacy extractor output only. Internal choice is paper structure, not a
    # CBSE-visible question type; ingestion splits it into normal questions.
    "internal_choice": 3,
}
QTYPE_BY_MARKS: dict[int, str] = {
    1: "mcq",
    2: "very_short_answer",
    3: "short_answer",
    4: "case_based",
    5: "long_answer",
}


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------



def _fingerprint(text: str) -> str:
    """MD5 of normalised text — used for de-duplication."""
    normalised = re.sub(r"\s+", " ", text.lower().strip())
    normalised = re.sub(r"[^\w\s]", "", normalised)
    return hashlib.md5(normalised.encode()).hexdigest()


def _detect_numerical(text: str) -> bool:
    """True if the question involves numerical calculation (SI units, equations)."""
    return bool(_NUMERICAL_RE.search(text))


def _mentions_diagram(text: str) -> bool:
    """True if the question text references a figure/diagram (image may be absent)."""
    return bool(_DIAGRAM_RE.search(text))


# ---------------------------------------------------------------------------
# Extractor seam
# ---------------------------------------------------------------------------


class Extractor(Protocol):
    """Turns PDF bytes into structured, tagged question dicts.

    Each dict carries: ``section``, ``qtype``, ``marks``, ``text``, ``options``,
    ``content`` (contract §9 region shape), ``chapter_slug``, ``cognitive_level``,
    ``topic_names``, ``primary_form``, and ``figures`` (bounding boxes the
    coordinator crops into assets). The coordinator sets ``parse_quality``.
    """

    def extract(self, pdf_bytes: bytes) -> list[dict]: ...


_PRIMARY_FORMS = ("none", "diagram_based", "table_based")

# Content regions a figure may anchor to: item-array + labelled regions (the
# model's `label` picks the option/subpart). `choices` nesting is out of scope
# (#77). Region names are owned by `bank.content`.
_FIGURE_REGIONS = content_mod.ITEM_REGIONS + content_mod.LABELLED_REGIONS


def _coerce_topic_names(value) -> list[str]:
    """Normalise a model ``topic_names`` value to a clean list of non-empty strings."""
    if not isinstance(value, list):
        return []
    return [s.strip() for s in value if isinstance(s, str) and s.strip()]


def _coerce_primary_form(value) -> str:
    """Clamp a model ``primary_form`` value to the known set; default ``none``."""
    return value if value in _PRIMARY_FORMS else "none"


def _coerce_cognitive_level(value) -> str:
    """Clamp fuzzy model cognitive levels to DB-safe short enum codes."""
    raw = str(value or CognitiveLevel.REMEMBER).strip()
    if raw in CognitiveLevel.values:
        return raw
    normalised = re.sub(r"[^a-z]", "", raw.lower())
    aliases = {
        "r": CognitiveLevel.REMEMBER,
        "remember": CognitiveLevel.REMEMBER,
        "remembering": CognitiveLevel.REMEMBER,
        "recall": CognitiveLevel.REMEMBER,
        "u": CognitiveLevel.UNDERSTAND,
        "understand": CognitiveLevel.UNDERSTAND,
        "understanding": CognitiveLevel.UNDERSTAND,
        "ap": CognitiveLevel.APPLY,
        "apply": CognitiveLevel.APPLY,
        "application": CognitiveLevel.APPLY,
        "applying": CognitiveLevel.APPLY,
        "an": CognitiveLevel.ANALYSE,
        "analyse": CognitiveLevel.ANALYSE,
        "analyze": CognitiveLevel.ANALYSE,
        "analysis": CognitiveLevel.ANALYSE,
        "analysing": CognitiveLevel.ANALYSE,
        "analyzing": CognitiveLevel.ANALYSE,
    }
    return aliases.get(normalised, CognitiveLevel.REMEMBER)


# Provider-enforced response schema (google-genai dict form). Top-level is an
# object so `LLMClient.extract` returns a dict; questions are schema-valid by
# construction. Tables (`rows`) are out of scope this slice — they fall back to
# rawText (see #77 for figure crops / richer content).
_CONTENT_ITEM = {
    "type": "OBJECT",
    "properties": {
        "type": {"type": "STRING"},
        "text": {"type": "STRING"},
        "latex": {"type": "STRING"},
    },
    "required": ["type"],
}
_CONTENT_ITEMS = {"type": "ARRAY", "items": _CONTENT_ITEM}
# ChoiceOption and SubQuestion share a shape: {label, marks?, content[]}.
_LABELLED_CONTENT = {
    "type": "OBJECT",
    "properties": {
        "label": {"type": "STRING"},
        "marks": {"type": "INTEGER"},
        "content": _CONTENT_ITEMS,
    },
    "required": ["label", "content"],
}
_CHOICE_GROUP = {
    "type": "OBJECT",
    "properties": {
        "displayStyle": {"type": "STRING"},
        "chooseCount": {"type": "INTEGER"},
        "options": {"type": "ARRAY", "items": _LABELLED_CONTENT},
    },
    "required": ["options"],
}
_FLAT_OPTION = {
    "type": "OBJECT",
    "properties": {
        "label": {"type": "STRING"},
        "text": {"type": "STRING"},
    },
    "required": ["label", "text"],
}
_QUESTION_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "questions": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "section": {"type": "STRING", "enum": ["A", "B", "C", "D", "E"]},
                    "qtype": {
                        "type": "STRING",
                        "enum": [
                            "mcq",
                            "assertion_reason",
                            "very_short_answer",
                            "short_answer",
                            "long_answer",
                            "case_based",
                        ],
                    },
                    "marks": {"type": "INTEGER"},
                    "rawText": {"type": "STRING"},
                    "options": {"type": "ARRAY", "items": _FLAT_OPTION},
                    "content": {
                        "type": "OBJECT",
                        "properties": {
                            "stem": _CONTENT_ITEMS,
                            "assertion": _CONTENT_ITEMS,
                            "reason": _CONTENT_ITEMS,
                            "passage": _CONTENT_ITEMS,
                            "options": {"type": "ARRAY", "items": _LABELLED_CONTENT},
                            "subparts": {"type": "ARRAY", "items": _LABELLED_CONTENT},
                            "choices": {"type": "ARRAY", "items": _CHOICE_GROUP},
                        },
                    },
                    # Closed-vocab enum is injected per call by
                    # ``build_question_schema`` from the live ``Chapter`` slugs —
                    # the base stays free-form so the module constant has no DB
                    # dependency at import (and ``test_question_shape`` can read it).
                    "chapter_slug": {"type": "STRING", "nullable": True},
                    "cognitive_level": {
                        "type": "STRING",
                        "enum": ["R", "U", "Ap", "An"],
                    },
                    "topic_names": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "primary_form": {
                        "type": "STRING",
                        "enum": list(_PRIMARY_FORMS),
                    },
                    # Figure bounding boxes for deterministic PyMuPDF cropping
                    # (#77). bbox is [x0, y0, x1, y1] normalized to [0, 1],
                    # top-left origin; page is 1-based.
                    "figures": {
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "page": {"type": "INTEGER"},
                                "bbox": {
                                    "type": "ARRAY",
                                    "items": {"type": "NUMBER"},
                                },
                                "region": {
                                    "type": "STRING",
                                    "enum": list(_FIGURE_REGIONS),
                                },
                                "label": {"type": "STRING"},
                                "caption": {"type": "STRING"},
                            },
                            "required": ["page", "bbox", "region"],
                        },
                    },
                },
                "required": ["section", "qtype", "marks", "rawText", "content"],
            },
        }
    },
    "required": ["questions"],
}


def build_question_schema(chapter_slugs) -> dict:
    """Return the response schema with ``chapter_slug`` closed to the taxonomy.

    ``chapter_slug`` is the one taxonomy field the model used to free-form, the
    root cause of the cross-paper chapter mis-tagging in #108. Closing it to the
    seeded ``Chapter`` slugs (built dynamically, never hardcoded, so it can't
    drift from migration ``0003``) stops bad values at the source — the Layer 1
    half of the fix; ``bank.guardrails`` is the deterministic safety net for
    anything that still slips through (e.g. legacy committed JSON).
    """
    schema = copy.deepcopy(_QUESTION_SCHEMA)
    props = schema["properties"]["questions"]["items"]["properties"]
    props["chapter_slug"] = {
        "type": "STRING",
        "enum": sorted(chapter_slugs),
        "nullable": True,
    }
    return schema


# ---------------------------------------------------------------------------
# google-genai dict form → standard JSON Schema (for the model seam, #156)
# ---------------------------------------------------------------------------

_GENAI_TO_JSON_TYPE = {
    "OBJECT": "object",
    "STRING": "string",
    "ARRAY": "array",
    "INTEGER": "integer",
    "NUMBER": "number",
    "BOOLEAN": "boolean",
}


def genai_to_json_schema(schema: dict) -> dict:
    """Translate a google-genai response-schema dict into standard JSON Schema.

    ``SeamExtractor`` emits structured output through LangChain
    ``with_structured_output(..., method="json_mode")``, which forwards the schema
    to the provider's native response-schema mechanism exactly like the bespoke
    path (``GeminiClient``) — but via ``langchain_google_genai``'s converter, which
    speaks *standard* JSON Schema. That converter (verified against
    langchain-google-genai 2.1.x) differs from feeding google-genai directly in
    three ways this translator compensates for, so ``build_question_schema``'s
    constraints survive intact:

    - it expects lower-case JSON-Schema ``type`` (and upper-cases internally), so
      genai ``OBJECT``/``STRING``/… are mapped down;
    - it re-derives each *nested* object's ``required`` as "every property without
      a ``default``", ignoring an explicit ``required`` list — so every property
      absent from an object's ``required`` is marked ``default: null`` here, making
      the derivation reproduce our ``required`` exactly;
    - it keeps an ``enum`` only at a property's own level and reads nullability
      from ``anyOf``/``type: null`` (not an OpenAPI ``nullable`` flag) — so a
      ``nullable`` field becomes ``{enum?, anyOf:[{type}, {type:"null"}]}``, the
      one form that survives with BOTH the closed ``enum`` and ``nullable`` intact.

    Pure (no I/O) — the single point translation correctness is asserted.
    """
    return _translate_node(schema)


def _translate_node(node: dict) -> dict:
    jtype = _GENAI_TO_JSON_TYPE.get(node.get("type"), "string")
    out: dict = {"type": jtype}

    if "enum" in node:
        out["enum"] = node["enum"]
    if jtype == "array" and "items" in node:
        out["items"] = _translate_node(node["items"])
    if jtype == "object":
        required = list(node.get("required", []))
        out["properties"] = {
            name: _translate_node(sub)
            for name, sub in node.get("properties", {}).items()
        }
        if required:
            out["required"] = required
        # The converter re-derives a nested object's required from the absence of
        # a default, so mark the optional properties to match our `required`.
        for name, prop in out["properties"].items():
            if name not in required:
                prop["default"] = None

    if node.get("nullable"):
        out = _as_nullable(out)
    return out


def _as_nullable(node: dict) -> dict:
    """Rewrite a translated node so nullability survives the converter.

    A bare ``anyOf:[{…,enum},{null}]`` loses the enum and ``{…,nullable:true}``
    loses nullability; hoisting ``enum`` beside an ``anyOf:[{type},{type:"null"}]``
    keeps both. The parent marks the field optional with a ``default`` afterwards.

    Only primitive nodes are supported: this rewrite keeps just ``type``/``enum``,
    so applying it to an object/array would silently drop ``properties``/``items``.
    The current schema only nullables ``chapter_slug`` (a string); rather than
    grow speculative nested handling, fail loud (Rule 12) if that ever changes.
    """
    if "properties" in node or "items" in node:
        raise ValueError(
            "genai_to_json_schema supports `nullable` only on primitive nodes; "
            f"got a {node.get('type')!r} node with nested structure."
        )
    nullable: dict = {"anyOf": [{"type": node["type"]}, {"type": "null"}]}
    if "enum" in node:
        nullable["enum"] = node["enum"]
    return nullable


def _coerce_figures(value) -> list[dict]:
    """Normalise a model ``figures`` value to clean, croppable box dicts.

    Keeps only entries with a 1-based int ``page``, a ``bbox`` of exactly four
    numbers forming a non-empty rectangle once clamped to ``[0, 1]``, and a known
    ``region``. ``label`` is coerced to a string. Anything malformed is dropped
    silently — the question's ``image_placeholder`` simply stays (fail-soft per
    ADR-0004; bad localisation is caught at human review).
    """
    if not isinstance(value, list):
        return []
    figures: list[dict] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        page = item.get("page")
        if not isinstance(page, int) or isinstance(page, bool) or page < 1:
            continue
        bbox = item.get("bbox")
        if not isinstance(bbox, list) or len(bbox) != 4:
            continue
        if not all(
            isinstance(n, (int, float)) and not isinstance(n, bool) for n in bbox
        ):
            continue
        x0, y0, x1, y1 = (min(1.0, max(0.0, float(n))) for n in bbox)
        if x0 >= x1 or y0 >= y1:
            continue
        region = item.get("region")
        if region not in _FIGURE_REGIONS:
            continue
        figure = {"page": page, "bbox": [x0, y0, x1, y1], "region": region}
        label = item.get("label")
        if isinstance(label, str) and label.strip():
            figure["label"] = label.strip()
        caption = item.get("caption")
        if isinstance(caption, str) and caption.strip():
            figure["caption"] = caption.strip()
        figures.append(figure)
    return figures


def _content_text(items: list[dict]) -> str:
    parts: list[str] = []
    for item in items:
        if isinstance(item, dict):
            text = str(item.get("text") or "").strip()
            if text:
                parts.append(text)
    return "\n".join(parts).strip()


def _split_internal_choice_question(q: dict) -> list[dict]:
    """Split a legacy internal-choice row into one normal question per option.

    Internal choice is not a CBSE-visible qtype; it is paper structure. Older
    extractor payloads store both OR alternatives under ``content.choices`` as
    one ``internal_choice`` row. At the ingestion boundary we flatten those into
    independent bank questions typed from their marks (3 → short_answer,
    5 → long_answer, etc.) so the picker can fill normal CBSE slots.
    """
    if q.get("qtype") != "internal_choice":
        return [q]

    content = q.get("content") or {}
    choices = content.get("choices") or []
    split: list[dict] = []
    target_qtype = QTYPE_BY_MARKS.get(q.get("marks"), "short_answer")

    for group in choices:
        if not isinstance(group, dict):
            continue
        for option in group.get("options") or []:
            if not isinstance(option, dict):
                continue
            option_content = option.get("content") or []
            if not isinstance(option_content, list):
                continue
            text = _content_text(option_content)
            if not text:
                continue
            label = str(option.get("label") or "").strip()
            figures: list[dict] = []
            for figure in q.get("figures", []):
                if figure.get("region") == "choices":
                    if label and figure.get("label") == label:
                        copied = dict(figure)
                        copied["region"] = "stem"
                        copied.pop("label", None)
                        figures.append(copied)
                else:
                    figures.append(dict(figure))
            split.append(
                {
                    **q,
                    "qtype": target_qtype,
                    "text": text,
                    "options": [],
                    "content": {"stem": option_content},
                    "figures": figures,
                }
            )

    return split or [{**q, "qtype": target_qtype}]


def _split_internal_choices(raw_questions: list[dict]) -> list[dict]:
    split: list[dict] = []
    for q in raw_questions:
        split.extend(_split_internal_choice_question(q))
    return split


def _coerce_question(obj: dict) -> dict:
    """Normalise one model-emitted question object to the coordinator dict shape.

    ``section`` is derived from ``marks`` (``MARKS_TO_SECTION``), not taken from
    the model: per-page extraction has no reliable section header to anchor on,
    but the printed mark value maps cleanly to a section. When the model omits a
    usable mark, the qtype implies one (``QTYPE_DEFAULT_MARKS``).
    """
    qtype = obj.get("qtype", "short_answer")
    try:
        marks = int(obj.get("marks"))
    except (TypeError, ValueError):
        marks = None
    if marks not in MARKS_TO_SECTION:
        marks = QTYPE_DEFAULT_MARKS.get(qtype, 3)
    section = MARKS_TO_SECTION[marks]
    # Strip a leading question number the model sometimes leaves on the stem
    # ("17. ..."). Requires whitespace after the dot, so decimals like "3.5 kg"
    # are left intact.
    text = re.sub(r"^\d{1,3}\.\s+", "", (obj.get("rawText", "") or "").strip())
    return {
        "section": section,
        "qtype": qtype,
        "marks": marks,
        "text": text,
        "options": obj.get("options", []) or [],
        "content": obj.get("content", {}) or {},
        "chapter_slug": obj.get("chapter_slug"),
        "cognitive_level": _coerce_cognitive_level(obj.get("cognitive_level")),
        "topic_names": _coerce_topic_names(obj.get("topic_names")),
        "primary_form": _coerce_primary_form(obj.get("primary_form")),
        "figures": _coerce_figures(obj.get("figures")),
    }


def merge_page_payloads(page_payloads: Iterable[dict]) -> list[dict]:
    """Coerce, page-rewrite, and de-duplicate per-page extraction payloads.

    Shared by both Extractors: ``page_payloads`` yields one ``{"questions": [...]}``
    dict per page, in document order. Each question is coerced to the coordinator
    shape, dropped if its stem is empty, de-duplicated across pages by text
    fingerprint (a question spilling across a page break is seen twice), and its
    figure page-refs rewritten from the single-page slice (page 1) to the absolute
    1-based document page so the cropper clips the right page.
    """
    questions: list[dict] = []
    seen: set[str] = set()
    for page_index, payload in enumerate(page_payloads):
        for obj in payload.get("questions", []):
            if not isinstance(obj, dict):
                continue
            question = _coerce_question(obj)
            if not question["text"].strip():
                continue
            fp = _fingerprint(question["text"])
            if fp in seen:
                continue
            seen.add(fp)
            for figure in question["figures"]:
                figure["page"] = page_index + 1
            questions.append(question)
    return questions


class GeminiExtractor:
    """Legacy Extractor — one bespoke native-PDF Gemini call per PAGE, merged in
    order. Kept revertable behind ``SeamExtractor`` until the #156 benchmark
    proves ``with_structured_output`` parity (ADR-0005).

    Page-at-a-time extraction forces a deep read of each page: on long scanned
    bilingual papers a single whole-document call skims and under-recalls (Hindi
    pages duplicate question numbers, later sections get dropped). Provider-bound
    via the bespoke `LLMClient`/`GeminiClient`.
    """

    def __init__(self, client: LLMClient | None = None):
        self.client = client or make_llm_client()

    def extract(self, pdf_bytes: bytes) -> list[dict]:
        prompt = _page_prompt()
        # Close chapter_slug to the live taxonomy so the model can only emit a
        # canonical slug (or null) — built once per paper, not per page.
        schema = build_question_schema(Chapter.objects.values_list("slug", flat=True))
        return merge_page_payloads(
            self.client.extract(page_bytes, prompt, schema)
            for page_bytes in _split_pages_for_runtime(pdf_bytes)
        )


# A model factory matching the seam's ``make_chat_model(purpose) -> BaseChatModel``,
# injectable so tests pass a fake (Rules 9/11; mirrors generate_answers).
MakeChatModel = Callable[[ModelPurpose], BaseChatModel]


def _page_message(prompt: str, page_bytes: bytes) -> list[HumanMessage]:
    """One multimodal turn: the extraction prompt plus the page as an inline PDF.

    ``langchain_google_genai`` reads a ``media`` content block's raw bytes into a
    Gemini ``Blob`` — the LangChain equivalent of the bespoke path's
    ``Part.from_bytes(..., mime_type="application/pdf")``.
    """
    return [
        HumanMessage(
            content=[
                {"type": "text", "text": prompt},
                {
                    "type": "media",
                    "mime_type": "application/pdf",
                    "data": page_bytes,
                },
            ]
        )
    ]


class SeamExtractor:
    """Default Extractor — native-PDF extraction on the model seam (#156).

    Builds the chat model via ``make_chat_model(ModelPurpose.EXTRACTION)`` and
    extracts one page at a time through LangChain ``with_structured_output(...,
    method="json_mode")``, which forwards the translated schema to the provider's
    native response-schema mechanism (Gemini today; swappable by config). The
    schema's closed ``chapter_slug`` enum and ``nullable``/``required`` constraints
    survive the JSON-Schema translation (``genai_to_json_schema``). Page-at-a-time
    extraction, coercion, figure page-rewrite, and dedup are shared with
    ``GeminiExtractor`` (``merge_page_payloads``). ``make_model`` is injectable so
    tests pass a fake factory — no module patching (Rules 9/11).
    """

    def __init__(self, make_model: MakeChatModel = make_chat_model):
        self._make_model = make_model

    def _structured(self):
        # Close chapter_slug to the live taxonomy, then translate to the standard
        # JSON Schema LangChain's structured-output converter speaks.
        json_schema = genai_to_json_schema(
            build_question_schema(Chapter.objects.values_list("slug", flat=True))
        )
        return self._make_model(ModelPurpose.EXTRACTION).with_structured_output(
            json_schema, method="json_mode"
        )

    def extract_page(self, page_bytes: bytes) -> dict:
        """One page slice → one raw ``{"questions": [...]}`` payload (one paid call).

        The page-sized unit the extraction workflow checkpoints (#157): each
        call is exactly one model invocation, so a resumed graph thread never
        re-pays for a page it already extracted. Coercion, figure page-rewrite,
        and dedup happen later over the accumulated payloads
        (``merge_page_payloads``) — the payload is checkpointed verbatim.
        """
        return self._structured().invoke(_page_message(_page_prompt(), page_bytes))

    def extract(self, pdf_bytes: bytes) -> list[dict]:
        # Structured model built once per paper, not per page.
        structured = self._structured()
        prompt = _page_prompt()
        return merge_page_payloads(
            structured.invoke(_page_message(prompt, page_bytes))
            for page_bytes in _split_pages_for_runtime(pdf_bytes)
        )
