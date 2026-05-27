"""Skeleton paper assembler.

Slice 1 only needs to fill a fixed set of slots from the seeded questions to
prove the end-to-end path. Slices 2 and 3 replace this with the real
BlueprintEngine + SelectionEngine.
"""
from django.db import transaction

from bank.models import Question, Section

from .models import Paper, PaperQuestion

# Fixed slot plan for the skeleton: how many questions to pull per section.
SKELETON_PLAN = [
    (Section.A, 4),
    (Section.B, 2),
    (Section.C, 2),
    (Section.D, 2),
    (Section.E, 1),
]


@transaction.atomic
def assemble_paper(user, title="Science — Practice Paper"):
    """Create a Paper by filling fixed slots from available bank questions."""
    paper = Paper.objects.create(
        created_by=user,
        school=getattr(user, "school", None),
        title=title,
    )

    order = 1
    total_marks = 0
    for section, count in SKELETON_PLAN:
        questions = list(
            Question.objects.filter(section=section).order_by("id")[:count]
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
