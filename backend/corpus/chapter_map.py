"""Deterministic derivation of a TextbookDocument's semantic chapter map.

The builder owns heading selection, partition ranges, stable identities, and
idempotent persistence. It uses only persisted TextbookElement evidence and
does not call an extractor, model provider, or renderer.
"""

from __future__ import annotations

import hashlib
import re

from django.db import transaction

from .models import ChapterMapEdge, ChapterMapNode, TextbookDocument, TextbookElement

_NUMBERED_HEADING = re.compile(r"^(\d+(?:\.\d+)*)\b")
_ACTIVITY = re.compile(r"^Activity\s+\d+\.\d+\b", re.IGNORECASE)
_FIGURE_CAPTION = re.compile(r"^(?:Fig(?:ure)?\.?)\s+\d+\.\d+\b", re.IGNORECASE)
_TABLE_CAPTION = re.compile(r"^Table\s+\d+\.\d+\b", re.IGNORECASE)
_SOURCE_REFERENCE = re.compile(
    r"\b(?P<kind>Fig(?:ure)?\.?|Table)\s*(?P<number>\d+\.\d+)\b",
    re.IGNORECASE,
)


class ChapterMapBuilder:
    """Rebuild one persisted chapter map from ordered source elements."""

    @transaction.atomic
    def rebuild(self, document: TextbookDocument) -> None:
        elements = list(document.elements.order_by("source_order"))
        if not elements:
            document.chapter_map_nodes.all().delete()
            return

        root = self._upsert_node(
            document=document,
            stable_node_id=self._stable_id("document", document.source_hash),
            node_type=ChapterMapNode.NodeType.DOCUMENT,
            title=document.chapter.name,
            parent=None,
            source_element=None,
            owned_elements=elements,
        )
        headings = [
            element
            for element in elements
            if element.element_type == "section_header"
            and _NUMBERED_HEADING.match(element.text)
        ]
        section_ids: set[str] = set()
        sections_by_number: dict[str, ChapterMapNode] = {}
        for index, heading in enumerate(headings):
            number = _NUMBERED_HEADING.match(heading.text).group(1)
            start = 0 if index == 0 else heading.source_order
            end = (
                headings[index + 1].source_order - 1
                if index + 1 < len(headings)
                else elements[-1].source_order
            )
            owned = [
                element for element in elements if start <= element.source_order <= end
            ]
            parent_number = number.rpartition(".")[0]
            parent = sections_by_number.get(parent_number, root)
            stable_node_id = self._stable_id("section", heading.stable_element_id)
            section = self._upsert_node(
                document=document,
                stable_node_id=stable_node_id,
                node_type=ChapterMapNode.NodeType.SECTION,
                title=heading.text,
                parent=parent,
                source_element=heading,
                owned_elements=owned,
            )
            section_ids.add(stable_node_id)
            sections_by_number[number] = section

        landmark_ids = self._rebuild_landmarks(document, root, elements)
        keep_ids = {root.stable_node_id, *section_ids, *landmark_ids}
        document.chapter_map_nodes.exclude(stable_node_id__in=keep_ids).delete()
        self._rebuild_edges(document, elements)

    def _rebuild_landmarks(
        self,
        document: TextbookDocument,
        root: ChapterMapNode,
        elements: list[TextbookElement],
    ) -> set[str]:
        sections = list(
            document.chapter_map_nodes.filter(node_type=ChapterMapNode.NodeType.SECTION)
        )
        landmark_ids: set[str] = set()
        for index, element in enumerate(elements):
            landmark = self._landmark_at(elements, index)
            if landmark is None:
                continue
            node_type, title, start, end = landmark
            parent = next(
                (
                    section
                    for section in sections
                    if section.source_start
                    <= element.source_order
                    <= section.source_end
                ),
                root,
            )
            owned = elements[start : end + 1]
            stable_node_id = self._stable_id(node_type, element.stable_element_id)
            self._upsert_node(
                document=document,
                stable_node_id=stable_node_id,
                node_type=node_type,
                title=title,
                parent=parent,
                source_element=element,
                owned_elements=owned,
            )
            landmark_ids.add(stable_node_id)
        return landmark_ids

    def _landmark_at(
        self, elements: list[TextbookElement], index: int
    ) -> tuple[str, str, int, int] | None:
        element = elements[index]
        if element.element_type == "section_header":
            if _ACTIVITY.match(element.text):
                return (
                    ChapterMapNode.NodeType.ACTIVITY,
                    element.text,
                    index,
                    self._before_next_landmark(elements, index),
                )
            compact = re.sub(r"[^A-Za-z]", "", element.text).upper()
            if compact == "QUESTIONS":
                return (
                    ChapterMapNode.NodeType.QUESTIONS,
                    "Questions",
                    index,
                    self._before_next_landmark(elements, index),
                )
            if compact == "EXERCISES":
                return (
                    ChapterMapNode.NodeType.EXERCISES,
                    "Exercises",
                    index,
                    self._before_next_landmark(elements, index),
                )
        if element.element_type in {"picture", "table"}:
            caption = self._adjacent_caption(elements, index, element.element_type)
            caption_index = elements.index(caption) if caption else index
            start, end = sorted((index, caption_index))
            title = (
                caption.text
                if caption
                else f"{element.element_type.title()} on page {element.page_number}"
            )
            node_type = (
                ChapterMapNode.NodeType.FIGURE
                if element.element_type == "picture"
                else ChapterMapNode.NodeType.TABLE
            )
            return node_type, title, start, end
        return None

    def _before_next_landmark(self, elements: list[TextbookElement], index: int) -> int:
        for candidate_index in range(index + 1, len(elements)):
            candidate = elements[candidate_index]
            if candidate.element_type == "section_header":
                return candidate_index - 1
        return len(elements) - 1

    @staticmethod
    def _adjacent_caption(
        elements: list[TextbookElement], index: int, element_type: str
    ) -> TextbookElement | None:
        pattern = _FIGURE_CAPTION if element_type == "picture" else _TABLE_CAPTION
        for candidate_index in (index + 1, index - 1):
            if 0 <= candidate_index < len(elements):
                candidate = elements[candidate_index]
                if candidate.element_type == "caption" and pattern.match(
                    candidate.text
                ):
                    return candidate
        return None

    def _rebuild_edges(
        self, document: TextbookDocument, elements: list[TextbookElement]
    ) -> None:
        nodes = list(document.chapter_map_nodes.select_related("parent"))
        edge_ids: set[str] = set()
        for node in nodes:
            if node.parent_id:
                edge_ids.add(
                    self._upsert_edge(
                        document,
                        ChapterMapEdge.EdgeType.CONTAINS,
                        node.parent,
                        node,
                    )
                )
        children_by_parent: dict[int, list[ChapterMapNode]] = {}
        for node in nodes:
            if node.parent_id:
                children_by_parent.setdefault(node.parent_id, []).append(node)
        for children in children_by_parent.values():
            children.sort(key=lambda node: (node.source_start, node.stable_node_id))
            for source, target in zip(children, children[1:]):
                edge_ids.add(
                    self._upsert_edge(
                        document, ChapterMapEdge.EdgeType.NEXT, source, target
                    )
                )
        landmark_candidates: dict[tuple[str, str], list[ChapterMapNode]] = {}
        for node in nodes:
            if node.node_type not in {
                ChapterMapNode.NodeType.FIGURE,
                ChapterMapNode.NodeType.TABLE,
            }:
                continue
            match = _SOURCE_REFERENCE.search(node.title)
            if match:
                landmark_candidates.setdefault(self._reference_key(match), []).append(
                    node
                )
        landmarks = {
            key: candidates[0]
            for key, candidates in landmark_candidates.items()
            if len(candidates) == 1
        }
        sections = [
            node for node in nodes if node.node_type == ChapterMapNode.NodeType.SECTION
        ]
        for element in elements:
            if element.element_type in {"caption", "section_header"}:
                continue
            for match in _SOURCE_REFERENCE.finditer(element.text):
                target = landmarks.get(self._reference_key(match))
                if target is None or (
                    target.source_start <= element.source_order <= target.source_end
                ):
                    continue
                source = next(
                    (
                        section
                        for section in sections
                        if section.source_start
                        <= element.source_order
                        <= section.source_end
                    ),
                    None,
                )
                if source is not None:
                    edge_ids.add(
                        self._upsert_edge(
                            document,
                            ChapterMapEdge.EdgeType.REFERENCES,
                            source,
                            target,
                            element,
                        )
                    )
        document.chapter_map_edges.exclude(stable_edge_id__in=edge_ids).delete()

    @staticmethod
    def _reference_key(match: re.Match[str]) -> tuple[str, str]:
        kind = match.group("kind").lower()
        return ("table" if kind == "table" else "figure", match.group("number"))

    def _upsert_edge(
        self,
        document: TextbookDocument,
        edge_type: str,
        source: ChapterMapNode,
        target: ChapterMapNode,
        evidence_element: TextbookElement | None = None,
    ) -> str:
        evidence_id = (
            evidence_element.stable_element_id if evidence_element is not None else ""
        )
        stable_edge_id = self._stable_id(
            edge_type,
            f"{source.stable_node_id}:{target.stable_node_id}:{evidence_id}",
        )
        ChapterMapEdge.objects.update_or_create(
            document=document,
            stable_edge_id=stable_edge_id,
            defaults={
                "edge_type": edge_type,
                "source": source,
                "target": target,
                "evidence_element": evidence_element,
            },
        )
        return stable_edge_id

    @staticmethod
    def _stable_id(kind: str, evidence: str) -> str:
        return hashlib.sha256(f"{kind}:{evidence}".encode()).hexdigest()

    @staticmethod
    def _upsert_node(
        *,
        document: TextbookDocument,
        stable_node_id: str,
        node_type: str,
        title: str,
        parent: ChapterMapNode | None,
        source_element: TextbookElement | None,
        owned_elements: list[TextbookElement],
    ) -> ChapterMapNode:
        pages = [element.page_number for element in owned_elements]
        preview = next((element.text for element in owned_elements if element.text), "")
        node, _ = ChapterMapNode.objects.update_or_create(
            document=document,
            stable_node_id=stable_node_id,
            defaults={
                "node_type": node_type,
                "title": title,
                "parent": parent,
                "source_element": source_element,
                "source_start": owned_elements[0].source_order,
                "source_end": owned_elements[-1].source_order,
                "page_start": min(pages),
                "page_end": max(pages),
                "element_count": len(owned_elements),
                "preview": preview[:240],
            },
        )
        return node
