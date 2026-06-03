"""Builds PaperDocumentV1 from assembled domain objects.

Mapping layer between internal domain objects and the frontend contract
defined in contracts/v1_contract.md. No DB writes; all IDs are derived.
"""

from __future__ import annotations

from collections import Counter, defaultdict

from bank import content as content_mod
from bank.models import Question
from bank.question_shape import fallback_regions

from .models import Paper
from .picker import FilledTemplate, PaperOptions
from .template import Slot

_SECTION_TITLE: dict[str, str] = {
    "A": "Section A",
    "B": "Section B",
    "C": "Section C",
    "D": "Section D",
    "E": "Section E",
}

_SECTION_INSTRUCTIONS: dict[str, str] = {
    "A": "Multiple Choice Questions. Select the correct option.",
    "B": "Very Short Answer type. Answer in 30–50 words.",
    "C": "Short Answer type. Answer in 50–80 words.",
    "D": "Long Answer type. Answer in 80–120 words.",
    "E": "Source/Case-based. Read the passage and answer the subparts.",
}

# QuestionDifficulty: the per-question difficulty label in the contract's
# metadata.difficulty (easy/medium/hard), derived from a Question's CognitiveLevel.
# Distinct from the paper-level DifficultyLevel (easy/standard/hard) the picker
# consumes — different grain, different value set. See CONTEXT.md.
_QUESTION_DIFFICULTY_BY_COG: dict[str, str] = {
    "R": "easy",
    "U": "medium",
    "Ap": "medium",
    "An": "hard",
}

# metadata.cognitiveLevel: the contract spells the Bloom level out; the bank
# stores the CBSE shorthand (R/U/Ap/An). One-way mapping for the document only.
_COGNITIVE_LEVEL_BY_COG: dict[str, str] = {
    "R": "remember",
    "U": "understand",
    "Ap": "apply",
    "An": "analyse",
}


class PaperDocumentBuilder:
    """Builds PaperDocumentV1 dict from internal domain objects."""

    def build(
        self,
        paper: Paper,
        result: FilledTemplate,
        inp: PaperOptions,
    ) -> dict:
        all_qids = self._all_question_ids(result)
        questions_by_pk = self._fetch_questions(all_qids)

        preset = result.template.preset

        return {
            "schemaVersion": "paper_document.v1",
            "request": self._build_request(paper, inp, preset.exam_type),
            "template": self._build_template(paper, preset),
            "format": self._build_format(),
            "paper": self._build_paper(paper, result, questions_by_pk),
            "questions": [self._build_question(q) for q in questions_by_pk.values()],
        }

    # --- internal helpers ---

    def _all_question_ids(self, result: FilledTemplate) -> list[int]:
        ids: set[int] = set()
        for qid in result.question_ids:
            if qid is not None:
                ids.add(qid)
        for alts in result.alternate_ids or []:
            ids.update(alts)
        return list(ids)

    def _fetch_questions(self, ids: list[int]) -> dict[int, Question]:
        if not ids:
            return {}
        return {
            q.pk: q
            for q in Question.objects.filter(pk__in=ids).select_related("chapter")
        }

    def _build_request(self, paper: Paper, inp: PaperOptions, exam_type: str) -> dict:
        return {
            "id": f"req_{paper.pk}",
            "language": "en",
            "classLevel": "10",
            "subject": "Science",
            "examType": exam_type,
            "filters": {
                "chapters": list(inp.chapter_slugs or []),
                "topics": [],
                "englishOnly": True,
            },
        }

    def _build_format(self) -> dict:
        # Contract §3: format.id selects the frontend renderer; page/layout carry
        # the compact CBSE board geometry and semantic layout roles only.
        return {
            "id": "cbse_science_class_10_board_compact_2026_v1",
            "page": {
                "size": "CBSE_COMPACT",
                "orientation": "portrait",
                "widthPt": 523.44,
                "heightPt": 693.36,
                "marginPt": {"top": 28, "right": 36, "bottom": 34, "left": 36},
            },
            "layout": {
                "marks": "right_column",
                "questionNumbers": "left_column",
                "mcqOptions": "two_column",
                "instructions": "note_table_then_general",
                "masthead": "cbse_compact",
                "footer": "code_page_pto",
            },
        }

    def _build_template(self, paper: Paper, preset) -> dict:
        return {
            "id": f"cbse_science_class_10_{preset.name}_v1",
            "name": preset.template_name,
            "board": "CBSE",
            "classLevel": "10",
            "subject": "Science",
            "examType": preset.exam_type,
            "totalMarks": paper.total_marks,
            "durationMinutes": preset.duration_minutes,
            "language": "en",
        }

    def _build_paper(
        self,
        paper: Paper,
        result: FilledTemplate,
        questions_by_pk: dict[int, Question],
    ) -> dict:
        duration = result.template.preset.duration_minutes
        return {
            "id": f"paper_{paper.pk}",
            "title": paper.title,
            "subtitle": "Class X",
            "totalMarks": paper.total_marks,
            "durationMinutes": duration,
            "language": "en",
            # Chrome = visible paper text keyed by CBSE role (contract §5).
            "chromeBlocks": [
                {"id": "subject_label", "role": "subject_label", "text": paper.title},
                {
                    "id": "paper_meta_left",
                    "role": "paper_meta_left",
                    "text": f"Time allowed: {duration // 60} hours",
                },
                {
                    "id": "paper_meta_right",
                    "role": "paper_meta_right",
                    "text": f"Maximum Marks: {paper.total_marks}",
                },
                {"id": "roll_number", "role": "roll_number", "text": "Roll No."},
            ],
            "instructionBlocks": [
                {
                    "id": "general_instructions_heading",
                    "role": "general_instructions_heading",
                    "text": "General Instructions:",
                },
                {
                    "id": "general_instruction_1",
                    "role": "general_instruction",
                    "text": "All questions are compulsory.",
                },
            ],
            "sections": self._build_sections(result, questions_by_pk),
        }

    def _build_sections(
        self,
        result: FilledTemplate,
        questions_by_pk: dict[int, Question],
    ) -> list[dict]:
        # Group slots by section, preserving PaperTemplate order.
        section_entries: dict[str, list[tuple[Slot, int | None, list[int]]]] = (
            defaultdict(list)
        )
        for idx, slot in enumerate(result.template.slots):
            qid = result.question_ids[idx]
            alts = result.alternate_ids[idx] if result.alternate_ids else []
            section_entries[slot.section].append((slot, qid, alts))

        sections = []
        display_counter = 1

        for section_key in ["A", "B", "C", "D", "E"]:
            entries = section_entries.get(section_key)
            if not entries:
                continue

            seen_or_groups: set[int] = set()
            section_marks = 0
            for slot, _, _ in entries:
                if slot.or_group is None:
                    section_marks += slot.marks
                elif slot.or_group not in seen_or_groups:
                    seen_or_groups.add(slot.or_group)
                    section_marks += slot.marks

            slots_data = []
            for local_idx, (slot, qid, alts) in enumerate(entries, start=1):
                slot_data: dict = {
                    "id": f"slot_{section_key}_{local_idx:02d}",
                    "number": str(display_counter),
                    "marks": slot.marks,
                    "type": slot.qtype,
                    "selectedQuestionId": f"q_{qid}" if qid is not None else None,
                    "alternateQuestionIds": [f"q_{aid}" for aid in alts],
                    "locked": False,
                    "can": {
                        "editText": True,
                        "editMarks": True,
                        "swap": True,
                        "lock": True,
                        "reorder": True,
                    },
                    "overrides": {"modified": False, "regions": {}},
                }
                if slot.or_group is not None:
                    slot_data["orGroup"] = slot.or_group
                slots_data.append(slot_data)
                display_counter += 1

            section: dict = {
                "id": section_key,
                "title": _SECTION_TITLE[section_key],
                "marks": section_marks,
                "instructions": _SECTION_INSTRUCTIONS[section_key],
                "slots": slots_data,
            }
            subtitle = self._section_subtitle(
                [qid for _, qid, _ in entries], questions_by_pk
            )
            if subtitle:
                section["subtitle"] = subtitle
            sections.append(section)

        return sections

    def _section_subtitle(
        self,
        qids: list[int | None],
        questions_by_pk: dict[int, Question],
    ) -> str | None:
        """Subtitle from the section's majority subject_area, else None.

        A subtitle is only emitted when one subject_area holds a strict majority
        of the section's tagged questions; mixed sections stay untitled (no
        hardcoded "Class X"). See contract §6.
        """
        areas = []
        for qid in qids:
            question = questions_by_pk.get(qid) if qid is not None else None
            if question and question.chapter and question.chapter.subject_area:
                areas.append(question.chapter.subject_area)
        if not areas:
            return None
        area, count = Counter(areas).most_common(1)[0]
        return area if count * 2 > len(areas) else None

    def _build_question(self, q: Question) -> dict:
        return {
            "id": f"q_{q.pk}",
            "language": "en",
            "defaultMarks": q.marks,
            "type": q.qtype,
            "rawText": q.text,
            "content": self._build_content(q),
            "metadata": self._build_metadata(q),
            "source": self._build_source(q),
        }

    def _build_content(self, q: Question) -> dict:
        """Return the question's structured content, region-keyed (contract §9).

        Ingested rows carry the full region map verbatim (stem/options/
        assertion/reason/passage/subparts/choices and any embedded image items),
        so it is passed through untouched — contract §10, source content
        preserved. Seed/back-compat rows with empty content fall back to a
        text-only stem, with diagram items synthesised from the bank flags.
        """
        if q.content:
            return q.content

        # Which regions to synthesise comes from the QuestionShape spec, so the
        # fallback can't drift from the qtype's real structure (see CONTEXT.md).
        regions = fallback_regions(q.qtype)
        content: dict = {"stem": [{"type": "paragraph", "text": q.text}]}
        if "options" in regions:
            content["options"] = [
                {
                    "label": opt.get("label", ""),
                    "content": [{"type": "paragraph", "text": opt.get("text", "")}],
                }
                for opt in (q.options or [])
            ]

        self._apply_diagram_fallback(q, content)
        return content

    def _apply_diagram_fallback(self, q: Question, content: dict) -> None:
        """Append a diagram item to the stem for rows without structured content.

        A cropped file resolves to an ``image`` item referencing the asset by
        storage name (``assetId``; no inline URL, contract §9). ``has_diagram``
        with no file yields an ``image_placeholder`` so the gap is visible.
        """
        stem = content.setdefault("stem", [])
        if q.diagram:
            stem.append({"type": "image", "assetId": q.diagram.name})
        elif q.has_diagram:
            stem.append(
                {
                    "type": "image_placeholder",
                    "text": "Diagram present in source PDF, extraction pending.",
                }
            )

    def _build_metadata(self, q: Question) -> dict:
        meta: dict = {
            "classLevel": "10",
            "subject": "Science",
            "chapterNames": [q.chapter.name] if q.chapter else [],
            "topicNames": list(q.topic_names or []),
            "difficulty": _QUESTION_DIFFICULTY_BY_COG.get(q.cognitive_level, "medium"),
            "cognitiveLevel": _COGNITIVE_LEVEL_BY_COG.get(
                q.cognitive_level, "understand"
            ),
            "requiresDiagram": q.has_diagram,
            "requiresTable": content_mod.has_item(q.content, "table"),
        }
        if q.chapter and q.chapter.subject_area:
            meta["subjectArea"] = q.chapter.subject_area
        return meta

    def _build_source(self, q: Question) -> dict:
        """Map a Question's provenance fields to the contract source object.

        Falls back to the bank's own identity for rows ingested before
        provenance was captured (blank source fields). Optional fields
        (fileName/pageNumber/originalQuestionNumber) are emitted only when set.
        """
        source: dict = {
            "type": q.source_type or "question_bank",
            "name": q.source_name or "School Science Question Bank",
        }
        if q.source_file_name:
            source["fileName"] = q.source_file_name
        if q.source_page_number is not None:
            source["pageNumber"] = q.source_page_number
        if q.source_original_qnum:
            source["originalQuestionNumber"] = q.source_original_qnum
        return source
