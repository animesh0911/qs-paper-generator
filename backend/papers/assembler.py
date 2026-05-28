"""Skeleton paper assembler.

Slice 1 only needs to fill a fixed set of slots from the seeded questions to
prove the end-to-end path. Slices 2 and 3 replace this with the real
BlueprintEngine + SelectionEngine.
"""
from django.db import transaction
from rest_framework.exceptions import ValidationError

from bank.models import Question, Section

from .models import Paper, PaperQuestion

# Fixed slot plan for the skeleton: how many questions to pull per section.
# This is the seam Slice 2/3 replaces — BlueprintEngine will produce a plan
# of the same ``[(section, count), ...]`` shape, so callers (and tests) can
# already pass an arbitrary plan into ``assemble_paper`` today.
SKELETON_PLAN = [
    (Section.A, 4),
    (Section.B, 2),
    (Section.C, 2),
    (Section.D, 2),
    (Section.E, 1),
]


@transaction.atomic
def assemble_paper(user, title="Science — Practice Paper", plan=SKELETON_PLAN):
    """Create a Paper by filling slots from available bank questions.

    Raises ``ValidationError`` (→ HTTP 400) when the bank cannot fill any
    section, rather than silently producing a short paper.
    """
    paper = Paper.objects.create(
        created_by=user,
        school=getattr(user, "school", None),
        title=title,
    )

    order = 1
    total_marks = 0
    for section, count in plan:
        questions = list(
            Question.objects.filter(section=section).order_by("id")[:count]
        )
        if len(questions) < count:
            raise ValidationError(
                f"Question bank only has {len(questions)}/{count} questions "
                f"for section {section}. Run `manage.py seed_questions` or "
                f"add more questions before assembling."
            )
        for q in questions:
            PaperQuestion.objects.create(
                paper=paper, question=q, order=order, section=section
            )
            total_marks += q.marks
            order += 1

    paper.total_marks = total_marks
    paper.save(update_fields=["total_marks"])
    return paper
