"""Unit tests for TemplateBuilder + PaperTemplate."""

from collections import Counter

import pytest

from bank.models import QuestionType, Section, SubjectArea
from papers.template import PRESET_NAMES, PaperTemplate, Preset, Slot, TemplateBuilder

# Board preset — acceptance criteria


def test_board_spec_total_marks():
    assert TemplateBuilder().build("board").total_marks == 80


def test_board_spec_question_count():
    assert TemplateBuilder().build("board").question_count == 39


def test_board_spec_uses_three_subject_sections():
    spec = TemplateBuilder().build("board")
    section_marks = {}
    for section in [Section.A, Section.B, Section.C]:
        seen_groups = set()
        total = 0
        for slot in [s for s in spec.slots if s.section == section]:
            if slot.or_group is None:
                total += slot.marks
            elif slot.or_group not in seen_groups:
                seen_groups.add(slot.or_group)
                total += slot.marks
        section_marks[section] = total

    assert section_marks == {Section.A: 30, Section.B: 25, Section.C: 25}
    assert {s.section for s in spec.slots} == {Section.A, Section.B, Section.C}
    assert {s.subject_area for s in spec.slots if s.section == Section.A} == {
        SubjectArea.BIOLOGY
    }
    assert {s.subject_area for s in spec.slots if s.section == Section.B} == {
        SubjectArea.CHEMISTRY
    }
    assert {s.subject_area for s in spec.slots if s.section == Section.C} == {
        SubjectArea.PHYSICS
    }


def test_board_spec_preserves_question_type_totals_for_candidate_lookup():
    spec = TemplateBuilder().build("board")
    by_type = Counter()
    seen_groups = set()
    for slot in spec.slots:
        if slot.or_group is None:
            by_type[slot.qtype] += slot.marks
        elif slot.or_group not in seen_groups:
            seen_groups.add(slot.or_group)
            by_type[slot.qtype] += slot.marks

    assert by_type == {
        QuestionType.MCQ: 20,
        QuestionType.VSA: 12,
        QuestionType.SA: 21,
        QuestionType.LA: 15,
        QuestionType.CASE: 12,
    }


def test_board_spec_maps_visible_sections_to_bank_question_type_sections():
    spec = TemplateBuilder().build("board")
    assert {s.bank_section for s in spec.slots if s.qtype == QuestionType.MCQ} == {
        Section.A
    }
    assert {s.bank_section for s in spec.slots if s.qtype == QuestionType.VSA} == {
        Section.B
    }
    assert {s.bank_section for s in spec.slots if s.qtype == QuestionType.SA} == {
        Section.C
    }
    assert {s.bank_section for s in spec.slots if s.qtype == QuestionType.LA} == {
        Section.D
    }
    assert {s.bank_section for s in spec.slots if s.qtype == QuestionType.CASE} == {
        Section.E
    }


# Additional presets


def test_half_yearly_total_marks():
    # 10×1 + 4×2 + 4×3 + 2×5 + 2×4 = 10+8+12+10+8 = 48
    assert TemplateBuilder().build("half_yearly").total_marks == 48


def test_half_yearly_question_count():
    # 10+4+4+2+2 = 22
    assert TemplateBuilder().build("half_yearly").question_count == 22


def test_unit_test_total_marks():
    # 5×1 + 2×2 + 2×3 + 1×5 = 5+4+6+5 = 20
    assert TemplateBuilder().build("unit_test").total_marks == 20


def test_unit_test_question_count():
    # 5+2+2+1 = 10
    assert TemplateBuilder().build("unit_test").question_count == 10


# OR-group invariants across all presets


def test_all_presets_or_groups_have_exactly_two_slots():
    for name in PRESET_NAMES:
        spec = TemplateBuilder().build(name)
        counts = Counter(s.or_group for s in spec.slots if s.or_group is not None)
        for grp, n in counts.items():
            assert n == 2, f"Preset {name!r} or_group={grp} has {n} slots, want 2"


def test_board_la_and_case_groups_do_not_overlap():
    spec = TemplateBuilder().build("board")
    la_groups = {
        s.or_group
        for s in spec.slots
        if s.qtype == QuestionType.LA and s.or_group is not None
    }
    case_groups = {
        s.or_group
        for s in spec.slots
        if s.qtype == QuestionType.CASE and s.or_group is not None
    }
    assert la_groups.isdisjoint(case_groups)


# Unknown preset


def test_unknown_preset_raises_value_error():
    with pytest.raises(ValueError, match="Unknown preset"):
        TemplateBuilder().build("nonexistent")


# PaperTemplate.total_marks / question_count logic


def test_paper_template_counts_or_marks_once():
    spec = PaperTemplate(
        preset=Preset(name="custom"),
        slots=[
            Slot(Section.A, QuestionType.MCQ, 1),
            Slot(Section.A, QuestionType.MCQ, 1),
            Slot(Section.D, QuestionType.LA, 5, or_group=0),
            Slot(Section.D, QuestionType.LA, 5, or_group=0),
        ],
    )
    assert spec.total_marks == 7  # 1 + 1 + 5 (not 12)
    assert spec.question_count == 3  # 2 standalone + 1 group


def test_paper_template_validate_rejects_odd_or_group():
    spec = PaperTemplate(
        preset=Preset(name="bad"),
        slots=[
            Slot(Section.D, QuestionType.LA, 5, or_group=0),
        ],
    )
    with pytest.raises(ValueError, match="OR groups"):
        spec.validate()


def test_all_standalone_spec():
    spec = PaperTemplate(
        preset=Preset(name="standalone"),
        slots=[Slot(Section.A, QuestionType.MCQ, 1) for _ in range(5)],
    )
    assert spec.total_marks == 5
    assert spec.question_count == 5
