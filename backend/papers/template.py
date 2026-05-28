"""Paper templates and presets.

A **Preset** bundles everything that defines a kind of paper: slot layout
(via `build_slots`), display name, exam-type tag for the V1 contract, and
duration. Single source of truth — used by both TemplateBuilder (which
turns it into a PaperTemplate) and PaperDocumentBuilder (which copies the
metadata into PaperDocumentV1).

TemplateBuilder.build(name) → PaperTemplate(preset, slots).
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Callable

from bank.models import QuestionType, Section


@dataclass
class Slot:
    """One question slot in a paper spec.

    or_group: slots sharing the same int are an "Answer A OR B" pair.
              None means the question is mandatory with no alternative.
    """

    section: str
    qtype: str
    marks: int
    or_group: int | None = None


def _board_slots() -> list[Slot]:
    slots: list[Slot] = []
    for _ in range(20):
        slots.append(Slot(Section.A, QuestionType.MCQ, 1))
    for _ in range(6):
        slots.append(Slot(Section.B, QuestionType.VSA, 2))
    for _ in range(7):
        slots.append(Slot(Section.C, QuestionType.SA, 3))
    for g in range(3):
        slots.append(Slot(Section.D, QuestionType.LA, 5, g))
        slots.append(Slot(Section.D, QuestionType.LA, 5, g))
    for g in range(3):
        slots.append(Slot(Section.E, QuestionType.CASE, 4, 3 + g))
        slots.append(Slot(Section.E, QuestionType.CASE, 4, 3 + g))
    return slots


def _half_yearly_slots() -> list[Slot]:
    slots: list[Slot] = []
    for _ in range(10):
        slots.append(Slot(Section.A, QuestionType.MCQ, 1))
    for _ in range(4):
        slots.append(Slot(Section.B, QuestionType.VSA, 2))
    for _ in range(4):
        slots.append(Slot(Section.C, QuestionType.SA, 3))
    for g in range(2):
        slots.append(Slot(Section.D, QuestionType.LA, 5, g))
        slots.append(Slot(Section.D, QuestionType.LA, 5, g))
    for g in range(2):
        slots.append(Slot(Section.E, QuestionType.CASE, 4, 2 + g))
        slots.append(Slot(Section.E, QuestionType.CASE, 4, 2 + g))
    return slots


def _unit_test_slots() -> list[Slot]:
    slots: list[Slot] = []
    for _ in range(5):
        slots.append(Slot(Section.A, QuestionType.MCQ, 1))
    for _ in range(2):
        slots.append(Slot(Section.B, QuestionType.VSA, 2))
    for _ in range(2):
        slots.append(Slot(Section.C, QuestionType.SA, 3))
    slots.append(Slot(Section.D, QuestionType.LA, 5, 0))
    slots.append(Slot(Section.D, QuestionType.LA, 5, 0))
    return slots


@dataclass(frozen=True)
class Preset:
    """A named recipe for a kind of paper.

    Bundles the slot layout with the display metadata PaperDocumentV1 needs,
    so adding a new preset = one literal in _PRESETS (not edits across files).

    Fields have empty/sensible defaults so tests can construct ad-hoc
    Presets for PaperTemplate fixtures without filling in every field.
    """

    name: str
    template_name: str = ""
    exam_type: str = ""
    duration_minutes: int = 180
    build_slots: Callable[[], list[Slot]] = lambda: []


@dataclass
class PaperTemplate:
    preset: Preset
    slots: list[Slot] = field(default_factory=list)

    @property
    def total_marks(self) -> int:
        seen: set[int] = set()
        total = 0
        for s in self.slots:
            if s.or_group is None:
                total += s.marks
            elif s.or_group not in seen:
                seen.add(s.or_group)
                total += s.marks
        return total

    @property
    def question_count(self) -> int:
        standalone = sum(1 for s in self.slots if s.or_group is None)
        groups = len({s.or_group for s in self.slots if s.or_group is not None})
        return standalone + groups

    def validate(self) -> None:
        group_counts = Counter(s.or_group for s in self.slots if s.or_group is not None)
        bad = [g for g, n in group_counts.items() if n != 2]
        if bad:
            raise ValueError(f"OR groups must have exactly 2 slots; bad groups: {bad}")


_PRESETS: dict[str, Preset] = {
    "board": Preset(
        name="board",
        template_name="CBSE Class 10 Science Full Term",
        exam_type="full_term",
        duration_minutes=180,
        build_slots=_board_slots,
    ),
    "half_yearly": Preset(
        name="half_yearly",
        template_name="CBSE Class 10 Science Half Yearly",
        exam_type="half_term",
        duration_minutes=120,
        build_slots=_half_yearly_slots,
    ),
    "unit_test": Preset(
        name="unit_test",
        template_name="CBSE Class 10 Science Unit Test",
        exam_type="unit_test",
        duration_minutes=60,
        build_slots=_unit_test_slots,
    ),
}

PRESET_NAMES: list[str] = list(_PRESETS)


class TemplateBuilder:
    def build(self, preset: str = "board") -> PaperTemplate:
        spec = _PRESETS.get(preset)
        if spec is None:
            raise ValueError(
                f"Unknown preset {preset!r}. Choose from: {PRESET_NAMES}"
            )
        template = PaperTemplate(preset=spec, slots=spec.build_slots())
        template.validate()
        return template
