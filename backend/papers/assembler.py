"""Paper assembly coordinator.

The view calls PaperAssembler().assemble(). All assembly logic lives inside
this class. _build_plan() returns the PaperSpec; _select() runs the
SelectionEngine; _persist() writes the Paper + PaperQuestion rows.
"""
from django.db import transaction

from .blueprint import BlueprintEngine, PaperSpec
from .models import Paper, PaperQuestion
from .selection import DEFAULT_PROFILE, SelectionEngine, SelectionInput, SelectionResult


class PaperAssembler:
    def assemble(
        self,
        user,
        title: str = "Science — Practice Paper",
        preset: str = "board",
        chapter_slugs: list[str] | None = None,
        weights: dict[str, float] | None = None,
        difficulty: str = DEFAULT_PROFILE,
    ) -> Paper:
        spec = self._build_plan(preset)
        result = self._select(spec, chapter_slugs, weights, difficulty)
        return self._persist(user, title, result)

    def _build_plan(self, preset: str) -> PaperSpec:
        return BlueprintEngine().build(preset)

    def _select(
        self,
        spec: PaperSpec,
        chapter_slugs: list[str] | None,
        weights: dict[str, float] | None,
        difficulty: str,
    ) -> SelectionResult:
        return SelectionEngine().select(
            SelectionInput(
                spec=spec,
                chapter_slugs=list(chapter_slugs or []),
                weights=weights,
                difficulty=difficulty,
            )
        )

    @transaction.atomic
    def _persist(self, user, title: str, result: SelectionResult) -> Paper:
        spec = result.spec
        paper = Paper.objects.create(
            created_by=user,
            school=getattr(user, "school", None),
            title=title,
            total_marks=spec.total_marks,
            report=result.report.to_dict(),
        )

        rows = []
        for i, (slot, qid) in enumerate(zip(spec.slots, result.question_ids)):
            if qid is None:
                continue
            rows.append(
                PaperQuestion(
                    paper=paper,
                    question_id=qid,
                    order=i + 1,
                    section=slot.section,
                    or_group=slot.or_group,
                )
            )
        if rows:
            PaperQuestion.objects.bulk_create(rows)
        return paper
