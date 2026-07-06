"""OCR-first extraction adapter for experiments.

This module deliberately plugs into the existing ingestion architecture instead
of reimplementing extraction/persistence:

    PDF page -> Mistral OCR markdown -> configured extraction chat model
        -> {"questions": [...]} -> bank.ingestor.merge_page_payloads(...)

The returned payload shape is the same shape ``SeamExtractor.extract_page``
returns, so the current LangGraph ``extract_page`` node can eventually swap this
adapter in without changing the persist tail.
"""

from __future__ import annotations

import base64
import json
import os
import re
import urllib.error
import urllib.request
from typing import Any

from django.db import OperationalError
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage

from ai_services.llm import ModelPurpose, make_chat_model

from .ingestor import build_question_schema, merge_page_payloads, split_pages
from .models import Chapter

_POC_CHAPTER_SLUGS = (
    "chemical-reactions-and-equations",
    "acids-bases-and-salts",
    "metals-and-non-metals",
    "carbon-and-its-compounds",
    "life-processes",
    "control-and-coordination",
    "how-do-organisms-reproduce",
    "heredity",
    "light-reflection-and-refraction",
    "human-eye-and-the-colourful-world",
    "electricity",
    "magnetic-effects-of-electric-current",
    "our-environment",
)


def _post_json(
    url: str, api_key: str, payload: dict[str, Any], *, timeout: int
) -> dict:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{url} returned HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"{url} request failed: {exc}") from exc


class MistralOcrClient:
    """Small HTTP client for Mistral's OCR endpoint."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: int = 300,
    ):
        self.api_key = (
            api_key
            or os.getenv("MISTRAL_API_KEY")
            or os.getenv("MISTRAL_OCR_API")
            or ""
        )
        self.base_url = (
            base_url or os.getenv("MISTRAL_BASE_URL") or "https://api.mistral.ai/v1"
        ).rstrip("/")
        self.model = model or os.getenv("MISTRAL_OCR_MODEL") or "mistral-ocr-latest"
        self.timeout = timeout
        if not self.api_key:
            raise ValueError("MISTRAL_API_KEY is required for OCR extraction.")

    def process_pdf(self, pdf_bytes: bytes) -> dict:
        encoded = base64.b64encode(pdf_bytes).decode("ascii")
        return _post_json(
            f"{self.base_url}/ocr",
            self.api_key,
            {
                "model": self.model,
                "document": {
                    "type": "document_url",
                    "document_url": f"data:application/pdf;base64,{encoded}",
                },
                "include_image_base64": False,
                "extract_header": False,
                "extract_footer": False,
                "table_format": "markdown",
            },
            timeout=self.timeout,
        )

    def markdown_for_pdf(self, pdf_bytes: bytes) -> str:
        pages = self.process_pdf(pdf_bytes).get("pages")
        if not isinstance(pages, list):
            return ""
        markdown_parts = []
        for page in pages:
            if isinstance(page, dict):
                markdown = page.get("markdown") or page.get("text") or ""
                if markdown:
                    markdown_parts.append(str(markdown))
        return "\n\n".join(markdown_parts).strip()


class MistralOcrMarkdownExtractor:
    """Extractor-compatible adapter: page PDF -> OCR markdown -> question JSON.

    ``extract_page`` intentionally returns the same raw page payload shape as
    ``SeamExtractor.extract_page``: ``{"questions": [...]}``. This lets the
    rest of the ingestion stack stay unchanged.
    """

    def __init__(
        self,
        *,
        ocr_client: MistralOcrClient | None = None,
        chat_model: BaseChatModel | None = None,
    ):
        self.ocr_client = ocr_client or MistralOcrClient()
        self.chat_model = chat_model or make_chat_model(ModelPurpose.EXTRACTION)

    def extract_page(self, page_bytes: bytes) -> dict:
        markdown = self.ocr_client.markdown_for_pdf(page_bytes)
        if not markdown:
            return {"questions": []}
        return self.structure_markdown(markdown)

    def extract(self, pdf_bytes: bytes) -> list[dict]:
        return merge_page_payloads(
            self.extract_page(page_bytes) for page_bytes in split_pages(pdf_bytes)
        )

    def structure_markdown(self, markdown: str) -> dict:
        if _looks_hindi_only(markdown):
            return {"questions": []}
        try:
            chapter_slugs = Chapter.objects.values_list("slug", flat=True)
            schema = build_question_schema(chapter_slugs)
        except OperationalError:
            # Local artifact-only POCs may run without the Docker/Postgres DB.
            # Keep the extraction test moving with the seeded taxonomy.
            schema = build_question_schema(_POC_CHAPTER_SLUGS)
        prompt = _markdown_extraction_prompt(markdown, schema)
        response = self.chat_model.invoke([HumanMessage(content=prompt)])
        return _drop_visual_questions(_parse_json_response(response.content))


def _markdown_extraction_prompt(markdown: str, schema: dict) -> str:
    return f"""
You are extracting questions from OCR markdown for a CBSE Class 10 Science
previous-year paper.

Rules:
- Extract EVERY English question visible in the OCR markdown.
- Ignore Hindi/Devanagari text. Never translate Hindi.
- If the page contains only Hindi/Devanagari questions, return
  {{"questions": []}}. Do not translate them into English.
- Ignore cover-page text, general instructions, headers, footers, page numbers,
  watermarks, and shared direction blocks that are not themselves questions.
- Copy question text verbatim. Do not paraphrase, complete, or correct the source.
- Do not include the printed question number or the marks digits in rawText.
- Never invent option labels, option text, marks, or missing halves of a
  question. If part of a question is cut off in the OCR text, copy only what
  is visible.
- Return JSON only with top-level shape: {{"questions": [...]}}.
- If OCR has an image placeholder such as `![img-12.jpeg](img-12.jpeg)`, never
  infer labels, values, structures, circuits, pH entries, or diagram details
  from it. Preserve only the text that is visible in OCR markdown.
- If a question depends on a diagram, figure, image, graph, circuit, ray diagram,
  labelled diagram, chemical structure image, experiment image, or visual table,
  mark it honestly with primary_form `diagram_based` or `table_based`; the
  deterministic post-filter will remove it before persistence.
- Set figures to [] for every returned question.
- Use content.stem at minimum:
  {{"stem": [{{"type": "paragraph", "text": rawText}}]}}.
- For MCQ/assertion-reason, include options both in `options` and, when possible,
  `content.options`.
- Pick chapter_slug only from the schema enum when obvious; otherwise use null.

Output schema/reference vocabulary:
{json.dumps(schema, ensure_ascii=False)}

OCR markdown:
```markdown
{markdown}
```
""".strip()


def _drop_visual_questions(payload: dict) -> dict:
    """Deterministically remove OCR outputs that still depend on visuals.

    The OCR markdown experiment is text-only for now. The prompt asks the model
    to skip visual questions, but this second gate prevents hallucinated diagram
    or image-dependent rows from reaching the Ingestor when the model misses the
    instruction.
    """
    questions = payload.get("questions")
    if not isinstance(questions, list):
        return {"questions": []}
    return {
        "questions": [
            question
            for question in questions
            if isinstance(question, dict) and not _is_visual_question(question)
        ]
    }


def _is_visual_question(question: dict) -> bool:
    """True when the question *depends on seeing* a visual the OCR text lacks.

    The patterns are reference-anchored on purpose: a question that merely
    mentions the word "diagram" ("Draw a labelled diagram of the human heart")
    is a complete text question a student can answer, so it must NOT be
    dropped. Only questions that point the student at a figure/table/graph
    that is not reproduced in the text ("shown in the figure", "the given
    circuit") are removed — those would otherwise persist as unanswerable
    rows, the OCR path's main hallucination-shaped failure.
    """
    primary_form = str(question.get("primary_form") or "").lower()
    if primary_form in {"diagram_based", "table_based"}:
        return True
    if question.get("figures"):
        return True
    haystack = "\n".join(_question_strings(question)).lower()
    visual_patterns = (
        r"!\[img-[^\]]*\]",
        r"\[image[^\]]*\]",
        r"\[diagram[^\]]*\]",
        r"\[circuit[^\]]*\]",
        # References to a visual the student is expected to look at.
        r"\b(?:shown|given)\s+(?:in|below\s+in)?\s*(?:the\s+)?"
        r"(?:figure|diagram|graph|circuit|image|table)\b",
        r"\b(?:figure|diagram|graph|circuit|image)\s+(?:given\s+)?"
        r"(?:above|below|alongside)\b",
        r"\bin\s+the\s+(?:following|given|above)\s+"
        r"(?:figure|diagram|graph|circuit)\b",
        r"\bobserve\s+the\s+(?:figure|diagram|graph|image|table)\b",
        r"\bon\s+the\s+basis\s+of\s+the\s+(?:figure|diagram|graph)\b",
        # Organic-structure identification needs the printed structures.
        r"\bname the following compounds\b",
    )
    return any(re.search(pattern, haystack) for pattern in visual_patterns)


def _question_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(_question_strings(item))
        return out
    if isinstance(value, dict):
        out = []
        for key, item in value.items():
            # Keys like "figures" are schema names, not source text. Looking at
            # them would classify every compliant question as visual.
            if key in {"figures", "primary_form"}:
                continue
            out.extend(_question_strings(item))
        return out
    return []


def pages_from_ocr_response(ocr: dict[str, Any]) -> list[dict[str, Any]]:
    pages = ocr.get("pages")
    if not isinstance(pages, list):
        return [{"index": 0, "markdown": json.dumps(ocr, ensure_ascii=False)}]
    out: list[dict[str, Any]] = []
    for i, page in enumerate(pages):
        if not isinstance(page, dict):
            continue
        markdown = page.get("markdown") or page.get("text") or ""
        out.append({"index": int(page.get("index", i)), "markdown": str(markdown)})
    return out


def is_hindi_only_page(markdown: str) -> bool:
    """Return True for pages where question text is Hindi-only.

    CBSE papers often repeat content in Hindi and English on adjacent pages.
    The experiment is scoped to English questions only; skipping Devanagari-
    dominated pages prevents the structuring LLM from translating duplicates.
    """
    devanagari = len(re.findall(r"[\u0900-\u097F]", markdown))
    latin = len(re.findall(r"[A-Za-z]", markdown))
    if devanagari < 40:
        return False
    return latin < max(40, devanagari // 6)


def is_english_question_page(markdown: str) -> bool:
    """Return True for pages worth sending to the English structuring LLM.

    Keep any English-heavy page, not only pages with an obvious question number:
    case-study passages, diagrams, or tables can be continuation/context pages.
    The LLM prompt is responsible for ignoring covers/instructions.
    """
    if not markdown.strip() or is_hindi_only_page(markdown):
        return False
    latin = len(re.findall(r"[A-Za-z]", markdown))
    if latin >= 80:
        return True
    patterns = (
        r"(^|\n)\s*(?:Q\.?\s*)?\d{1,2}\s*[.)]",
        r"Questions?\s+no",
        r"SECTION\s+[A-E]",
        r"Assertion\s*\(A\)",
        r"\*\*OR\*\*|\bOR\b",
    )
    return any(re.search(pattern, markdown, re.IGNORECASE) for pattern in patterns)


def batch_ocr_markdown(pages: list[dict[str, Any]]) -> str:
    parts = []
    for page in pages:
        page_no = int(page["index"]) + 1
        parts.append(f"\n\n===== OCR PAGE {page_no} =====\n\n{page['markdown']}")
    return "".join(parts).strip()


# Backwards-compatible private alias used inside this module.
_looks_hindi_only = is_hindi_only_page


def _parse_json_response(content: Any) -> dict:
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        text = "\n".join(
            str(part.get("text") if isinstance(part, dict) else part)
            for part in content
        )
    else:
        text = str(content)

    cleaned = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)\s*```", cleaned, re.DOTALL)
    if fence:
        cleaned = fence.group(1).strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            try:
                parsed = json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError as inner_exc:
                msg = f"Structuring model returned non-JSON: {text[:800]}"
                raise RuntimeError(msg) from inner_exc
        else:
            msg = f"Structuring model returned non-JSON: {text[:800]}"
            raise RuntimeError(msg) from exc
    if not isinstance(parsed, dict):
        return {"questions": []}
    if not isinstance(parsed.get("questions"), list):
        parsed["questions"] = []
    return parsed
