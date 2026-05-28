"""Paper assembly coordinator.

The view calls PaperAssembler().assemble(). All assembly logic lives inside
this class. _build_plan() is the seam: Slices 2/3 replace it with
BlueprintEngine without touching the view or this coordinator's interface.
"""
from django.db import transaction
from rest_framework.exceptions import ValidationError

from bank.models import Question, Section

from .models import Paper, PaperQuestion

SKELETON_PLAN = [
    (Section.A, 4),
    (Section.B, 2),
    (Section.C, 2),
    (Section.D, 2),
    (Section.E, 1),
]


class PaperAssembler:
    def assemble(self, user, title: str = "Science — Practice Paper") -> Paper:
        plan = self._build_plan()
        return self._fill_slots(user, title, plan)

    def _build_plan(self):
        # Slice 2 replaces this with BlueprintEngine(user, config).plan()
        return SKELETON_PLAN

    @transaction.atomic
    def _fill_slots(self, user, title, plan) -> Paper:
        """Create a Paper by filling slots from available bank questions.

        Raises ValidationError (→ HTTP 400) when the bank cannot fill any
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
