"""Paper assembly coordinator.

The view calls PaperAssembler().assemble(). All assembly logic lives inside
this class. _build_plan() is the seam: Slice 3 replaces it with
SelectionEngine without touching the view or this coordinator's interface.
"""
from collections import defaultdict
from collections import deque

from django.db import transaction
from rest_framework.exceptions import ValidationError

from bank.models import Question

from .blueprint import BlueprintEngine, PaperSpec, Slot
from .models import Paper, PaperQuestion

_SlotKey = tuple[str, str, int]  # (section, qtype, marks)


def _slot_key(slot: Slot) -> _SlotKey:
    return (slot.section, slot.qtype, slot.marks)


class PaperAssembler:
    def assemble(
        self, user, title: str = "Science — Practice Paper", preset: str = "board"
    ) -> Paper:
        spec = self._build_plan(preset)
        return self._fill_slots(user, title, spec)

    def _build_plan(self, preset: str) -> PaperSpec:
        return BlueprintEngine().build(preset)

    @transaction.atomic
    def _fill_slots(self, user, title: str, spec: PaperSpec) -> Paper:
        """Create a Paper by filling each slot from the bank.

        Fetches one query per unique (section, qtype, marks) key, then
        allocates from in-memory pools. OR-group slots draw distinct
        questions from the same pool.
        """
        # Count how many questions each slot key needs.
        needed: dict[_SlotKey, int] = defaultdict(int)
        for slot in spec.slots:
            needed[_slot_key(slot)] += 1

        # One SELECT per unique key.
        pools: dict[_SlotKey, deque[int]] = {}
        for key, count in needed.items():
            section, qtype, marks = key
            ids = list(
                Question.objects.filter(section=section, qtype=qtype, marks=marks)
                .order_by("id")
                .values_list("id", flat=True)[:count]
            )
            if len(ids) < count:
                raise ValidationError(
                    f"Question bank only has {len(ids)}/{count} questions for "
                    f"section={section}, qtype={qtype}, marks={marks}. "
                    f"Add more questions or run `manage.py seed_questions`."
                )
            pools[key] = deque(ids)

        paper = Paper.objects.create(
            created_by=user,
            school=getattr(user, "school", None),
            title=title,
        )

        rows = [
            PaperQuestion(
                paper=paper,
                question_id=pools[_slot_key(slot)].popleft(),
                order=i + 1,
                section=slot.section,
                or_group=slot.or_group,
            )
            for i, slot in enumerate(spec.slots)
        ]
        PaperQuestion.objects.bulk_create(rows)

        paper.total_marks = spec.total_marks
        paper.save(update_fields=["total_marks"])
        return paper
