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


def canonical_json_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_docling_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text())
    if data.get("schema_name") != "DoclingDocument":
        raise ValueError("canonical JSON must use the DoclingDocument schema")
    return data
