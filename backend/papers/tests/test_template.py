"""Unit tests for TemplateBuilder + PaperTemplate."""
from collections import Counter

import pytest

from bank.models import QuestionType, Section
from papers.template import PaperTemplate, PRESET_NAMES, Preset, Slot, TemplateBuilder


# ---------------------------------------------------------------------------
# Board preset — acceptance criteria
# ---------------------------------------------------------------------------


def test_board_spec_total_marks():
    assert TemplateBuilder().build("board").total_marks == 80


def test_board_spec_question_count():
    assert TemplateBuilder().build("board").question_count == 39


def test_board_spec_section_a_20_mcq_1m():
    spec = TemplateBuilder().build("board")
    a = [s for s in spec.slots if s.section == Section.A]
    assert len(a) == 20
    assert all(s.marks == 1 and s.qtype == QuestionType.MCQ and s.or_group is None for s in a)


def test_board_spec_section_b_6_vsa_2m():
    spec = TemplateBuilder().build("board")
    b = [s for s in spec.slots if s.section == Section.B]
    assert len(b) == 6
    assert all(s.marks == 2 and s.qtype == QuestionType.VSA and s.or_group is None for s in b)


def test_board_spec_section_c_7_sa_3m():
    spec = TemplateBuilder().build("board")
    c = [s for s in spec.slots if s.section == Section.C]
    assert len(c) == 7
    assert all(s.marks == 3 and s.qtype == QuestionType.SA and s.or_group is None for s in c)


def test_board_spec_section_d_3_la_5m_with_or():
    spec = TemplateBuilder().build("board")
    d = [s for s in spec.slots if s.section == Section.D]
    assert len(d) == 6
    groups = {s.or_group for s in d}
    assert None not in groups
    assert len(groups) == 3


def test_board_spec_section_e_3_case_4m_with_or():
    spec = TemplateBuilder().build("board")
    e = [s for s in spec.slots if s.section == Section.E]
    assert len(e) == 6
    groups = {s.or_group for s in e}
    assert None not in groups
    assert len(groups) == 3


# ---------------------------------------------------------------------------
# Additional presets
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# OR-group invariants across all presets
# ---------------------------------------------------------------------------


def test_all_presets_or_groups_have_exactly_two_slots():
    for name in PRESET_NAMES:
        spec = TemplateBuilder().build(name)
        counts = Counter(s.or_group for s in spec.slots if s.or_group is not None)
        for grp, n in counts.items():
            assert n == 2, f"Preset {name!r} or_group={grp} has {n} slots, want 2"


def test_d_and_e_groups_do_not_overlap():
    spec = TemplateBuilder().build("board")
    d_groups = {s.or_group for s in spec.slots if s.section == Section.D and s.or_group is not None}
    e_groups = {s.or_group for s in spec.slots if s.section == Section.E and s.or_group is not None}
    assert d_groups.isdisjoint(e_groups)


# ---------------------------------------------------------------------------
# Unknown preset
# ---------------------------------------------------------------------------


def test_unknown_preset_raises_value_error():
    with pytest.raises(ValueError, match="Unknown preset"):
        TemplateBuilder().build("nonexistent")


# ---------------------------------------------------------------------------
# PaperTemplate.total_marks / question_count logic
# ---------------------------------------------------------------------------


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
