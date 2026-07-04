"""Deterministic normalization of canonical Docling JSON into TextbookElements.

The normalizer is a pure boundary between Docling's document schema and the
corpus models. It follows Docling's body/group references for source order,
preserves source evidence, and applies only demonstrated cleanup rules.

Where it fits:
- Called by: ``corpus.importer.CorpusImporter``.
- Produces: immutable values persisted as ``TextbookElement`` rows.
- Does not call: Docling, an LLM, storage, or the database.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_NON_CONTENT_LABELS = {"page_header", "page_footer"}
_DECORATIVE_NOISE = re.compile(r"^[PD\s]{12,}$")
_NUMBERED_HEADING = re.compile(r"^(\d+(?:\.\d+)*)\b")


@dataclass(frozen=True)
class NormalizedTextbookElement:
    stable_element_id: str
    element_type: str
    source_order: int
    page_number: int
    bbox: dict[str, Any]
    heading_path: list[str]
    text: str
    structured_data: dict[str, Any]
    asset_path: str


class DoclingNormalizer:
    """Convert one DoclingDocument dict into stable ordered element values."""

    def __init__(self, source_hash: str):
        self.source_hash = source_hash

    def normalize(self, document: dict[str, Any]) -> list[NormalizedTextbookElement]:
        lookup = self._lookup(document)
        ordered = self._ordered_nodes(document, lookup)
        heading_stack: list[tuple[int, str, bool]] = []
        result: list[NormalizedTextbookElement] = []

        for node in ordered:
            label = str(node.get("label", "unknown"))
            if label in _NON_CONTENT_LABELS:
                continue
            text = self._clean_text(str(node.get("text", "")))
            if not text and label not in {"table", "picture"}:
                continue
            if _DECORATIVE_NOISE.fullmatch(text):
                continue

            heading_path = [heading for _, heading, _ in heading_stack]
            if label == "section_header":
                numbered = bool(_NUMBERED_HEADING.match(text))
                level = self._heading_level(heading_stack, text)
                while heading_stack and (
                    heading_stack[-1][0] >= level
                    or (numbered and not heading_stack[-1][2])
                ):
                    heading_stack.pop()
                heading_stack.append((level, text, numbered))
                heading_path = [heading for _, heading, _ in heading_stack]

            prov = (node.get("prov") or [{}])[0]
            self_ref = str(node.get("self_ref", ""))
            result.append(
                NormalizedTextbookElement(
                    stable_element_id=self._stable_id(self_ref),
                    element_type=label,
                    source_order=len(result),
                    page_number=int(prov.get("page_no") or 0),
                    bbox=dict(prov.get("bbox") or {}),
                    heading_path=heading_path,
                    text=text,
                    structured_data=self._structured_data(node, label),
                    asset_path=self._asset_path(node),
                )
            )
        return result

    def _stable_id(self, self_ref: str) -> str:
        return hashlib.sha256(f"{self.source_hash}:{self_ref}".encode()).hexdigest()

    @staticmethod
    def _lookup(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
        lookup: dict[str, dict[str, Any]] = {}
        for collection in (
            "texts",
            "tables",
            "pictures",
            "groups",
            "form_items",
            "key_value_items",
        ):
            for node in document.get(collection, []):
                if node.get("self_ref"):
                    lookup[node["self_ref"]] = node
        return lookup

    @staticmethod
    def _ordered_nodes(
        document: dict[str, Any], lookup: dict[str, dict[str, Any]]
    ) -> list[dict[str, Any]]:
        ordered: list[dict[str, Any]] = []
        seen: set[str] = set()

        def visit(reference: dict[str, str]) -> None:
            ref = reference.get("$ref", "")
            if not ref or ref in seen:
                return
            seen.add(ref)
            node = lookup.get(ref)
            if not node:
                return
            if node.get("label") != "group":
                ordered.append(node)
            for child in node.get("children", []):
                visit(child)

        for child in document.get("body", {}).get("children", []):
            visit(child)
        return ordered

    @staticmethod
    def _clean_text(value: str) -> str:
        text = " ".join(value.split())
        words = text.split()
        if (
            len(words) >= 4
            and len(words) % 2 == 0
            and words[: len(words) // 2] == words[len(words) // 2 :]
        ):
            text = " ".join(words[: len(words) // 2])
        return text

    @staticmethod
    def _heading_level(current: list[tuple[int, str, bool]], heading: str) -> int:
        match = _NUMBERED_HEADING.match(heading)
        if match:
            return match.group(1).count(".") + 1
        numbered_levels = [level for level, _, numbered in current if numbered]
        return (numbered_levels[-1] if numbered_levels else 0) + 1

    @staticmethod
    def _structured_data(node: dict[str, Any], label: str) -> dict[str, Any]:
        if label == "table":
            return {"data": node.get("data", {})}
        if label == "picture":
            image = dict(node.get("image", {}))
            if image.get("uri"):
                image["uri"] = Path(image["uri"]).name
            return {
                "captions": node.get("captions", []),
                "references": node.get("references", []),
                "image": image,
            }
        return {key: node[key] for key in ("orig", "content_layer") if key in node}

    @staticmethod
    def _asset_path(node: dict[str, Any]) -> str:
        uri = (node.get("image") or {}).get("uri", "")
        return Path(uri).name if uri else ""


class MistralOcrMarkdownNormalizer:
    """Convert Mistral OCR page markdown into stable textbook element values.

    Mistral OCR is page-oriented markdown, not a structural document graph. This
    normalizer intentionally keeps a conservative, auditable mapping: headings,
    captions, image placeholders, markdown tables, and paragraph blocks are
    preserved in source order without inventing missing diagram/table content.
    """

    _MARKDOWN_HEADING = re.compile(r"^#{1,6}\s+")
    _NUMBERED_SECTION = re.compile(r"^(\d+(?:\.\d+)+)\s+\S")
    _LANDMARK_HEADING = re.compile(
        r"^(?:Activity\s+\d+\.\d+|Questions?|"
        r"Q\s*U\s*E\s*S\s*T\s*I\s*O\s*N\s*S|Exercises?)\b",
        re.IGNORECASE,
    )
    _FIGURE_CAPTION = re.compile(r"^(?:Fig(?:ure)?\.?)\s+\d+\.\d+\b", re.IGNORECASE)
    _TABLE_CAPTION = re.compile(r"^Table\s+\d+\.\d+\b", re.IGNORECASE)
    _IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
    _PAGE_NOISE = re.compile(
        r"^(?:SCIENCE|Chapter\s+\d+|\d+|\d{3,}\w+|"
        r"Reprint\s+\d{4}-\d{2}|Rationalised\s+\d{4}-\d{2}|"
        r"The Human Eye and the Colourful World)$",
        re.IGNORECASE,
    )

    def __init__(self, source_hash: str):
        self.source_hash = source_hash

    def normalize(self, ocr: dict[str, Any]) -> list[NormalizedTextbookElement]:
        pages = self._drop_think_it_over_sidebar(pages_from_mistral_ocr(ocr))
        blocks: list[tuple[int, str, str, dict[str, Any]]] = []
        for page in pages:
            blocks.extend(self._page_blocks(page["page_number"], page["markdown"]))

        heading_stack: list[tuple[int, str, bool]] = []
        result: list[NormalizedTextbookElement] = []
        for page_number, element_type, text, structured_data in blocks:
            cleaned = self._clean_block_text(text)
            if not cleaned and element_type not in {"table", "picture"}:
                continue
            if element_type == "text" and self._PAGE_NOISE.fullmatch(cleaned):
                continue

            heading_path = [heading for _, heading, _ in heading_stack]
            if element_type == "section_header":
                numbered = bool(_NUMBERED_HEADING.match(cleaned))
                level = DoclingNormalizer._heading_level(heading_stack, cleaned)
                while heading_stack and (
                    heading_stack[-1][0] >= level
                    or (numbered and not heading_stack[-1][2])
                ):
                    heading_stack.pop()
                heading_stack.append((level, cleaned, numbered))
                heading_path = [heading for _, heading, _ in heading_stack]

            source_order = len(result)
            stable_ref = f"mistral://page/{page_number}/block/{source_order}"
            result.append(
                NormalizedTextbookElement(
                    stable_element_id=self._stable_id(stable_ref, cleaned),
                    element_type=element_type,
                    source_order=source_order,
                    page_number=page_number,
                    bbox={},
                    heading_path=heading_path,
                    text=cleaned,
                    structured_data=structured_data,
                    asset_path=self._asset_path(structured_data),
                )
            )
        return result

    def _drop_think_it_over_sidebar(
        self, pages: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        cleaned_pages: list[dict[str, Any]] = []
        skipping = False
        for page in pages:
            kept_lines: list[str] = []
            for line in str(page["markdown"]).splitlines():
                stripped = self._strip_markdown(line.strip())
                if re.fullmatch(r"Think it over", stripped, re.IGNORECASE):
                    skipping = True
                    continue
                if skipping and self._NUMBERED_SECTION.match(stripped):
                    skipping = False
                if not skipping:
                    kept_lines.append(line)
            cleaned_pages.append(
                {**page, "markdown": "\n".join(kept_lines).strip()}
            )
        return cleaned_pages

    def _page_blocks(
        self, page_number: int, markdown: str
    ) -> list[tuple[int, str, str, dict[str, Any]]]:
        blocks: list[tuple[int, str, str, dict[str, Any]]] = []
        paragraph: list[str] = []
        table: list[str] = []

        def flush_paragraph() -> None:
            nonlocal paragraph
            text = " ".join(part.strip() for part in paragraph if part.strip())
            if text:
                blocks.append((page_number, self._classify_text(text), text, {}))
            paragraph = []

        def flush_table() -> None:
            nonlocal table
            if table:
                text = "\n".join(table)
                blocks.append((page_number, "table", text, {"markdown": text}))
            table = []

        for raw_line in markdown.splitlines():
            line = raw_line.strip()
            if not line:
                flush_paragraph()
                flush_table()
                continue
            if self._is_markdown_table_line(line):
                flush_paragraph()
                table.append(line)
                continue
            flush_table()
            text = self._strip_markdown(line)
            if not text or self._PAGE_NOISE.fullmatch(text):
                continue
            if self._IMAGE.search(text):
                flush_paragraph()
                blocks.append(
                    (page_number, "picture", "", {"markdown": text, "image": text})
                )
                continue
            kind = self._classify_text(text)
            if kind in {"section_header", "caption"}:
                flush_paragraph()
                blocks.append((page_number, kind, text, {}))
                continue
            paragraph.append(text)
        flush_paragraph()
        flush_table()
        return blocks

    def _classify_text(self, text: str) -> str:
        clean = self._clean_block_text(text)
        if self._NUMBERED_SECTION.match(clean) or self._LANDMARK_HEADING.match(clean):
            return "section_header"
        if self._FIGURE_CAPTION.match(clean) or self._TABLE_CAPTION.match(clean):
            return "caption"
        return "text"

    @classmethod
    def _strip_markdown(cls, line: str) -> str:
        line = cls._MARKDOWN_HEADING.sub("", line).strip()
        line = re.sub(r"^[-*+]\s+", "", line).strip()
        line = re.sub(r"\*\*([^*]+)\*\*", r"\1", line)
        line = re.sub(r"__([^_]+)__", r"\1", line)
        return line.strip()

    @staticmethod
    def _is_markdown_table_line(line: str) -> bool:
        return line.startswith("|") and line.endswith("|") and line.count("|") >= 2

    @staticmethod
    def _clean_block_text(value: str) -> str:
        lines = [" ".join(line.split()) for line in value.splitlines()]
        return "\n".join(line for line in lines if line).strip()

    def _stable_id(self, stable_ref: str, text: str) -> str:
        evidence = f"{self.source_hash}:{stable_ref}:{text[:120]}"
        return hashlib.sha256(evidence.encode()).hexdigest()

    @staticmethod
    def _asset_path(structured_data: dict[str, Any]) -> str:
        image = str(structured_data.get("image", ""))
        match = re.search(r"\(([^)]+)\)", image)
        return Path(match.group(1)).name if match else ""


def pages_from_mistral_ocr(ocr: dict[str, Any]) -> list[dict[str, Any]]:
    pages = ocr.get("pages")
    if not isinstance(pages, list):
        return [{"page_number": 1, "markdown": json.dumps(ocr, ensure_ascii=False)}]
    result: list[dict[str, Any]] = []
    for index, page in enumerate(pages):
        if not isinstance(page, dict):
            continue
        markdown = page.get("markdown") or page.get("text") or ""
        result.append(
            {
                "page_number": int(page.get("index", index)) + 1,
                "markdown": str(markdown),
            }
        )
    return result


def canonical_json_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_docling_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text())
    if data.get("schema_name") != "DoclingDocument":
        raise ValueError("canonical JSON must use the DoclingDocument schema")
    return data


def load_mistral_ocr_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError("Mistral OCR artifact must be a JSON object")
    return data
