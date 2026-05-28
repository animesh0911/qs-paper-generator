"""Paper templates and presets.

TemplateBuilder.build(preset) → PaperTemplate
PaperTemplate is the skeleton the PaperBuilder and QuestionPicker consume.
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


@dataclass
class PaperTemplate:
    name: str
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


def _board_spec() -> PaperTemplate:
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
    return PaperTemplate(name="board", slots=slots)


def _half_yearly_spec() -> PaperTemplate:
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
    return PaperTemplate(name="half_yearly", slots=slots)


def _unit_test_spec() -> PaperTemplate:
    slots: list[Slot] = []
    for _ in range(5):
        slots.append(Slot(Section.A, QuestionType.MCQ, 1))
    for _ in range(2):
        slots.append(Slot(Section.B, QuestionType.VSA, 2))
    for _ in range(2):
        slots.append(Slot(Section.C, QuestionType.SA, 3))
    slots.append(Slot(Section.D, QuestionType.LA, 5, 0))
    slots.append(Slot(Section.D, QuestionType.LA, 5, 0))
    return PaperTemplate(name="unit_test", slots=slots)


_PRESETS: dict[str, Callable[[], PaperTemplate]] = {
    "board": _board_spec,
    "half_yearly": _half_yearly_spec,
    "unit_test": _unit_test_spec,
}

PRESET_NAMES: list[str] = list(_PRESETS)


class TemplateBuilder:
    def build(self, preset: str = "board") -> PaperTemplate:
        factory = _PRESETS.get(preset)
        if factory is None:
            raise ValueError(
                f"Unknown preset {preset!r}. Choose from: {PRESET_NAMES}"
            )
        spec = factory()
        spec.validate()
        return spec
