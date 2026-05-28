"""Builds PaperAssemblyBundleV1 from assembled domain objects.

Mapping layer between internal domain objects and the frontend contract
defined in contracts/v1_contract.md. No DB writes; all IDs are derived.
"""
from __future__ import annotations

from collections import defaultdict

from bank.models import Question

from .blueprint import Slot
from .models import Paper
from .selection import SelectionInput, SelectionResult


_QTYPE_CONTRACT: dict[str, str] = {
    "MCQ": "mcq",
    "VSA": "very_short_answer",
    "SA": "short_answer",
    "LA": "long_answer",
    "CASE": "case_based",
}

_PRESET_EXAM_TYPE: dict[str, str] = {
    "board": "full_term",
    "half_yearly": "half_term",
    "unit_test": "unit_test",
}

_PRESET_TEMPLATE_NAME: dict[str, str] = {
    "board": "CBSE Class 10 Science Full Term",
    "half_yearly": "CBSE Class 10 Science Half Yearly",
    "unit_test": "CBSE Class 10 Science Unit Test",
}

_PRESET_DURATION: dict[str, int] = {
    "board": 180,
    "half_yearly": 120,
    "unit_test": 60,
}

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

_COG_TO_DIFFICULTY: dict[str, str] = {
    "R": "easy",
    "U": "medium",
    "Ap": "medium",
    "An": "hard",
}


class BundleBuilder:
    """Builds PaperAssemblyBundleV1 dict from internal domain objects."""

    def build(
        self,
        paper: Paper,
        result: SelectionResult,
        inp: SelectionInput,
    ) -> dict:
        all_qids = self._all_question_ids(result)
        questions_by_pk = self._fetch_questions(all_qids)

        preset = result.spec.name
        exam_type = _PRESET_EXAM_TYPE.get(preset, preset)

        return {
            "schemaVersion": "paper_assembly_bundle.v1",
            "request": self._build_request(paper, inp, exam_type),
            "template": self._build_template(paper, preset, exam_type),
            "paper": self._build_paper(paper, result),
            "questions": [
                self._build_question(q) for q in questions_by_pk.values()
            ],
        }

    # --- internal helpers ---

    def _all_question_ids(self, result: SelectionResult) -> list[int]:
        ids: set[int] = set()
        for qid in result.question_ids:
            if qid is not None:
                ids.add(qid)
        for alts in (result.alternate_ids or []):
            ids.update(alts)
        return list(ids)

    def _fetch_questions(self, ids: list[int]) -> dict[int, Question]:
        if not ids:
            return {}
        return {
            q.pk: q
            for q in Question.objects.filter(pk__in=ids).select_related("chapter")
        }

    def _build_request(self, paper: Paper, inp: SelectionInput, exam_type: str) -> dict:
        return {
            "requestId": f"req_{paper.pk}",
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

    def _build_template(self, paper: Paper, preset: str, exam_type: str) -> dict:
        return {
            "templateId": f"cbse_science_class_10_{preset}_v1",
            "templateName": _PRESET_TEMPLATE_NAME.get(preset, preset),
            "board": "CBSE",
            "classLevel": "10",
            "subject": "Science",
            "examType": exam_type,
            "totalMarks": paper.total_marks,
            "durationMinutes": _PRESET_DURATION.get(preset, 180),
            "language": "en",
        }

    def _build_paper(self, paper: Paper, result: SelectionResult) -> dict:
        preset = result.spec.name
        duration = _PRESET_DURATION.get(preset, 180)
        return {
            "paperId": f"paper_{paper.pk}",
            "title": paper.title,
            "subtitle": "Class X",
            "totalMarks": paper.total_marks,
            "durationMinutes": duration,
            "language": "en",
            "headerBlocks": [
                {
                    "blockId": "header_001",
                    "blockType": "paper_header",
                    "text": f"{paper.title} — Class X",
                    "editable": True,
                }
            ],
            "instructionBlocks": [
                {
                    "blockId": "instruction_001",
                    "blockType": "instruction",
                    "text": (
                        f"Maximum Marks: {paper.total_marks}. "
                        f"Time allowed: {duration // 60} hours."
                    ),
                    "editable": True,
                }
            ],
            "sections": self._build_sections(result),
        }

    def _build_sections(self, result: SelectionResult) -> list[dict]:
        # Group slots by section, preserving PaperSpec order.
        section_entries: dict[str, list[tuple[Slot, int | None, list[int]]]] = (
            defaultdict(list)
        )
        for idx, slot in enumerate(result.spec.slots):
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
                contract_qtype = _QTYPE_CONTRACT.get(slot.qtype, slot.qtype.lower())
                slot_data: dict = {
                    "slotId": f"slot_{section_key}_{local_idx:02d}",
                    "displayNumber": str(display_counter),
                    "marks": slot.marks,
                    "questionType": contract_qtype,
                    "selectedQuestionId": f"q_{qid}" if qid is not None else None,
                    "locked": False,
                }
                if alts:
                    slot_data["alternateQuestionIds"] = [f"q_{aid}" for aid in alts]
                if slot.or_group is not None:
                    slot_data["orGroup"] = slot.or_group
                slots_data.append(slot_data)
                display_counter += 1

            sections.append({
                "sectionId": section_key,
                "title": _SECTION_TITLE[section_key],
                "marks": section_marks,
                "instructions": _SECTION_INSTRUCTIONS[section_key],
                "slots": slots_data,
            })

        return sections

    def _build_question(self, q: Question) -> dict:
        return {
            "questionId": f"q_{q.pk}",
            "language": "en",
            "marks": q.marks,
            "questionType": _QTYPE_CONTRACT.get(q.qtype, q.qtype.lower()),
            "rawText": q.text,
            "content": self._build_content(q),
            "metadata": self._build_metadata(q),
            "source": self._build_source(q),
        }

    def _build_content(self, q: Question) -> dict:
        if q.qtype == "MCQ":
            return {
                "stem": [{"type": "paragraph", "text": q.text}],
                "options": [
                    {
                        "label": opt.get("label", ""),
                        "content": [{"type": "paragraph", "text": opt.get("text", "")}],
                    }
                    for opt in (q.options or [])
                ],
            }
        return {"stem": [{"type": "paragraph", "text": q.text}]}

    def _build_metadata(self, q: Question) -> dict:
        return {
            "classLevel": "10",
            "subject": "Science",
            "chapterNames": [q.chapter.name] if q.chapter else [],
            "topicNames": [],
            "difficulty": _COG_TO_DIFFICULTY.get(q.cognitive_level, "medium"),
        }

    def _build_source(self, q: Question) -> dict:
        return {
            "sourceType": "question_bank",
            "sourceName": "School Science Question Bank",
        }
