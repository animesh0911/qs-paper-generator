"""Question selection over a PaperSpec.

SelectionEngine fills each Slot from the bank honouring chapter weights and
the cognitive-level distribution implied by the difficulty profile, with no
in-paper duplicates. Best-effort: unfillable slots are reported, not raised.

Seam: PaperAssembler calls SelectionEngine().select(SelectionInput) and uses
the returned ids + report.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from bank.models import Question

from .blueprint import PaperSpec

# Cognitive-level mix per difficulty profile. Codes match CognitiveLevel.
DIFFICULTY_PROFILES: dict[str, dict[str, float]] = {
    "easy":     {"R": 0.50, "U": 0.35, "Ap": 0.10, "An": 0.05},
    "standard": {"R": 0.25, "U": 0.35, "Ap": 0.25, "An": 0.15},
    "hard":     {"R": 0.10, "U": 0.25, "Ap": 0.35, "An": 0.30},
}
DEFAULT_PROFILE = "standard"
PROFILE_NAMES: list[str] = list(DIFFICULTY_PROFILES)


@dataclass
class SelectionInput:
    spec: PaperSpec
    # Empty list means "all chapters". Strings are Chapter.slug values.
    chapter_slugs: list[str] = field(default_factory=list)
    # Per-chapter weights keyed by slug. None or missing keys default to 1.
    # Normalised by the engine so absolute scale doesn't matter.
    weights: dict[str, float] | None = None
    difficulty: str = DEFAULT_PROFILE


@dataclass
class SelectionResult:
    spec: PaperSpec
    # Parallel to spec.slots; None means the slot is unfilled.
    question_ids: list[int | None]
    coverage: dict[str, int] = field(default_factory=dict)        # chapter slug -> count
    cog_coverage: dict[str, int] = field(default_factory=dict)    # level code -> count
    unfilled: list[dict] = field(default_factory=list)


_BucketKey = tuple[str, str, int]


class SelectionEngine:
    def select(self, inp: SelectionInput) -> SelectionResult:
        if inp.difficulty not in DIFFICULTY_PROFILES:
            raise ValueError(
                f"Unknown difficulty {inp.difficulty!r}. Choose from {PROFILE_NAMES}"
            )
        profile = DIFFICULTY_PROFILES[inp.difficulty]

        # Group slot indices by (section, qtype, marks) so we fetch one
        # candidate pool per bucket rather than one per slot.
        bucket_slot_indices: dict[_BucketKey, list[int]] = defaultdict(list)
        for idx, slot in enumerate(inp.spec.slots):
            bucket_slot_indices[(slot.section, slot.qtype, slot.marks)].append(idx)

        bucket_candidates: dict[_BucketKey, list[tuple[int, str | None, str]]] = {}
        for key in bucket_slot_indices:
            section, qtype, marks = key
            qs = Question.objects.filter(section=section, qtype=qtype, marks=marks)
            if inp.chapter_slugs:
                qs = qs.filter(chapter__slug__in=inp.chapter_slugs)
            bucket_candidates[key] = list(
                qs.order_by("id").values_list("id", "chapter__slug", "cognitive_level")
            )

        chapter_weights = self._normalise_weights(inp, bucket_candidates)

        question_ids: list[int | None] = [None] * len(inp.spec.slots)
        used: set[int] = set()
        coverage: dict[str, int] = defaultdict(int)
        cog_coverage: dict[str, int] = defaultdict(int)
        unfilled: list[dict] = []

        for key, slot_indices in bucket_slot_indices.items():
            section, qtype, marks = key
            n = len(slot_indices)
            chapter_target = self._allocate(n, chapter_weights)
            cog_target = self._allocate(n, profile)
            candidates = bucket_candidates[key]

            for slot_idx in slot_indices:
                pick = self._pick(candidates, used, chapter_target, cog_target)
                if pick is None:
                    unfilled.append(
                        {
                            "slot_index": slot_idx,
                            "section": section,
                            "qtype": qtype,
                            "marks": marks,
                            "reason": "no candidate in bank matching constraints",
                        }
                    )
                    continue
                qid, ch_slug, level = pick
                question_ids[slot_idx] = qid
                used.add(qid)
                if ch_slug:
                    coverage[ch_slug] += 1
                    if chapter_target.get(ch_slug, 0) > 0:
                        chapter_target[ch_slug] -= 1
                cog_coverage[level] += 1
                if cog_target.get(level, 0) > 0:
                    cog_target[level] -= 1

        return SelectionResult(
            spec=inp.spec,
            question_ids=question_ids,
            coverage=dict(coverage),
            cog_coverage=dict(cog_coverage),
            unfilled=unfilled,
        )

    @staticmethod
    def _normalise_weights(
        inp: SelectionInput,
        bucket_candidates: dict[_BucketKey, list[tuple[int, str | None, str]]],
    ) -> dict[str, float]:
        if inp.chapter_slugs:
            slugs = list(inp.chapter_slugs)
        else:
            seen = {
                slug
                for rows in bucket_candidates.values()
                for _, slug, _ in rows
                if slug
            }
            slugs = sorted(seen)
        if not slugs:
            return {}
        raw = {
            s: max(0.0, float((inp.weights or {}).get(s, 1.0))) for s in slugs
        }
        total = sum(raw.values())
        if total <= 0:
            return {s: 1.0 / len(slugs) for s in slugs}
        return {s: v / total for s, v in raw.items()}

    @staticmethod
    def _allocate(n: int, ratios: dict[str, float]) -> dict[str, int]:
        """Largest-remainder allocation so quotas sum to exactly n."""
        if not ratios or n == 0:
            return {k: 0 for k in ratios}
        raw = {k: ratios[k] * n for k in ratios}
        floors = {k: int(v) for k, v in raw.items()}
        leftover = n - sum(floors.values())
        rema = sorted(
            ratios.keys(), key=lambda k: (-(raw[k] - floors[k]), k)
        )
        for k in rema[:leftover]:
            floors[k] += 1
        return floors

    @staticmethod
    def _pick(
        candidates: list[tuple[int, str | None, str]],
        used: set[int],
        chapter_target: dict[str, int],
        cog_target: dict[str, int],
    ) -> tuple[int, str | None, str] | None:
        """Pick the unused candidate that best fills remaining quotas.

        Priority: highest remaining chapter quota, then highest remaining
        cognitive-level quota, then lowest id (deterministic).
        """
        best: tuple[int, str | None, str] | None = None
        best_key: tuple[int, int, int] | None = None
        for qid, ch_slug, level in candidates:
            if qid in used:
                continue
            ch_score = chapter_target.get(ch_slug, 0) if ch_slug else 0
            cog_score = cog_target.get(level, 0)
            key = (-ch_score, -cog_score, qid)
            if best_key is None or key < best_key:
                best = (qid, ch_slug, level)
                best_key = key
        return best
