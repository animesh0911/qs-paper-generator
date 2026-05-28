"""Question selection over a PaperTemplate.

QuestionPicker fills each Slot from the bank honouring chapter weights and
the cognitive-level distribution implied by the difficulty level, with no
in-paper duplicates. Best-effort: unfillable slots are reported, not raised.

Internal seam: ``_fetch_candidates`` produces an in-memory ``QuestionPool``
from the ORM; ``_select_from_pool`` is the pure allocator the picker runs
over that pool. Tests can hand-build a pool and exercise the allocator
without touching the database.

External seam: PaperBuilder calls QuestionPicker().select(PaperOptions)
and uses the returned ids + report.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from bank.models import Question

from .template import PaperTemplate

# Cognitive-level mix per difficulty level. Codes match CognitiveLevel.
DIFFICULTY_LEVELS: dict[str, dict[str, float]] = {
    "easy":     {"R": 0.50, "U": 0.35, "Ap": 0.10, "An": 0.05},
    "standard": {"R": 0.25, "U": 0.35, "Ap": 0.25, "An": 0.15},
    "hard":     {"R": 0.10, "U": 0.25, "Ap": 0.35, "An": 0.30},
}
DEFAULT_DIFFICULTY = "standard"
DIFFICULTY_NAMES: list[str] = list(DIFFICULTY_LEVELS)


@dataclass
class PaperOptions:
    template: PaperTemplate
    # Empty list means "all chapters". Strings are Chapter.slug values.
    chapter_slugs: list[str] = field(default_factory=list)
    # Per-chapter weights keyed by slug. None or missing keys default to 1.
    # Normalised by the picker so absolute scale doesn't matter.
    weights: dict[str, float] | None = None
    difficulty: str = DEFAULT_DIFFICULTY


@dataclass
class CoverageReport:
    """Coverage report persisted on Paper and returned to the client.

    Single source of truth for the report shape. ``to_dict`` produces the
    canonical JSON form for storage; ``from_dict`` reconstructs the object.
    Round-trippable so storage and the picker can never disagree.
    """

    coverage: dict[str, int] = field(default_factory=dict)        # chapter slug -> count
    cog_coverage: dict[str, int] = field(default_factory=dict)    # level code -> count
    unfilled: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "coverage": dict(self.coverage),
            "cog_coverage": dict(self.cog_coverage),
            "unfilled": list(self.unfilled),
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> "CoverageReport":
        data = data or {}
        return cls(
            coverage=dict(data.get("coverage", {})),
            cog_coverage=dict(data.get("cog_coverage", {})),
            unfilled=list(data.get("unfilled", [])),
        )


_N_ALTERNATES = 3


@dataclass
class FilledTemplate:
    template: PaperTemplate
    # Parallel to template.slots; None means the slot is unfilled.
    question_ids: list[int | None]
    # Parallel to template.slots; swap candidates for each slot (not persisted).
    alternate_ids: list[list[int]] = field(default_factory=list)
    report: CoverageReport = field(default_factory=CoverageReport)

    # Convenience pass-throughs used by callers and tests so they don't need
    # to reach into result.report.X every time.
    @property
    def coverage(self) -> dict[str, int]:
        return self.report.coverage

    @property
    def cog_coverage(self) -> dict[str, int]:
        return self.report.cog_coverage

    @property
    def unfilled(self) -> list[dict]:
        return self.report.unfilled


_BucketKey = tuple[str, str, int]
# A pool row: (question_id, chapter_slug or None, cognitive_level code).
PoolRow = tuple[int, str | None, str]
# In-memory question pool keyed by bucket.
QuestionPool = dict[_BucketKey, list[PoolRow]]


class QuestionPicker:
    def select(self, opts: PaperOptions) -> FilledTemplate:
        if opts.difficulty not in DIFFICULTY_LEVELS:
            raise ValueError(
                f"Unknown difficulty {opts.difficulty!r}. Choose from {DIFFICULTY_NAMES}"
            )
        pool = self._fetch_candidates(opts)
        return self._select_from_pool(opts, pool)

    @staticmethod
    def _fetch_candidates(opts: PaperOptions) -> QuestionPool:
        """Issue one ORM query per (section, qtype, marks) bucket."""
        buckets: set[_BucketKey] = {
            (s.section, s.qtype, s.marks) for s in opts.template.slots
        }
        pool: QuestionPool = {}
        for key in buckets:
            section, qtype, marks = key
            qs = Question.objects.filter(section=section, qtype=qtype, marks=marks)
            if opts.chapter_slugs:
                qs = qs.filter(chapter__slug__in=opts.chapter_slugs)
            pool[key] = list(
                qs.order_by("id").values_list("id", "chapter__slug", "cognitive_level")
            )
        return pool

    @classmethod
    def _select_from_pool(
        cls, opts: PaperOptions, pool: QuestionPool
    ) -> FilledTemplate:
        """Pure allocator: take a pool and options, produce the report.

        No ORM access. All tests of allocation invariants — chapter weighting,
        cognitive mix, no-dup, unfilled reporting — flow through this method.
        """
        profile = DIFFICULTY_LEVELS[opts.difficulty]

        bucket_slot_indices: dict[_BucketKey, list[int]] = defaultdict(list)
        for idx, slot in enumerate(opts.template.slots):
            bucket_slot_indices[(slot.section, slot.qtype, slot.marks)].append(idx)

        chapter_weights = cls._normalise_weights(opts, pool)

        question_ids: list[int | None] = [None] * len(opts.template.slots)
        used: set[int] = set()
        coverage: dict[str, int] = defaultdict(int)
        cog_coverage: dict[str, int] = defaultdict(int)
        unfilled: list[dict] = []

        for key, slot_indices in bucket_slot_indices.items():
            section, qtype, marks = key
            n = len(slot_indices)
            chapter_target = cls._allocate(n, chapter_weights)
            cog_target = cls._allocate(n, profile)
            candidates = pool.get(key, [])

            for slot_idx in slot_indices:
                pick = cls._pick(candidates, used, chapter_target, cog_target)
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

        alternate_ids: list[list[int]] = [[] for _ in range(len(opts.template.slots))]
        for key, slot_indices in bucket_slot_indices.items():
            candidates = pool.get(key, [])
            alt_pool = [qid for qid, _, _ in candidates if qid not in used]
            for slot_idx in slot_indices:
                alternate_ids[slot_idx] = alt_pool[:_N_ALTERNATES]

        return FilledTemplate(
            template=opts.template,
            question_ids=question_ids,
            alternate_ids=alternate_ids,
            report=CoverageReport(
                coverage=dict(coverage),
                cog_coverage=dict(cog_coverage),
                unfilled=unfilled,
            ),
        )

    @staticmethod
    def _normalise_weights(
        opts: PaperOptions,
        pool: QuestionPool,
    ) -> dict[str, float]:
        if opts.chapter_slugs:
            slugs = list(opts.chapter_slugs)
        else:
            seen = {
                slug
                for rows in pool.values()
                for _, slug, _ in rows
                if slug
            }
            slugs = sorted(seen)
        if not slugs:
            return {}
        raw = {
            s: max(0.0, float((opts.weights or {}).get(s, 1.0))) for s in slugs
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
        candidates: list[PoolRow],
        used: set[int],
        chapter_target: dict[str, int],
        cog_target: dict[str, int],
    ) -> PoolRow | None:
        """Pick the unused candidate that best fills remaining quotas.

        Priority: highest remaining chapter quota, then highest remaining
        cognitive-level quota, then lowest id (deterministic).
        """
        best: PoolRow | None = None
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
