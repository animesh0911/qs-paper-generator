"""The generation metric suite: decomposed judge + deterministic floors.

Design (from the 2026-07-10 judge–human calibration):

- One G-Eval per subjective rubric dimension instead of one holistic prompt —
  scores stop averaging away each other's failures, and each dimension gets
  its own pass threshold.
- The calibration's two systematic judge errors are written into the
  evaluation steps: fidelity must respect the *citation contract* (a
  chapter-true fact cited to the wrong excerpt is a grounding failure), and
  difficulty must penalize near-verbatim lifts and unshown-data recall (the
  Table 4.1 failure the old judge missed).
- Faithfulness (claim decomposition) localizes *which* claim is unsupported.
- Structure and lexical citation support are pure code — deterministic, free,
  and reusing production's own screen (``bank.citation_support``).
"""

from __future__ import annotations

from deepeval.metrics import BaseMetric, FaithfulnessMetric, GEval
from deepeval.test_case import LLMTestCase, SingleTurnParams

from evals.deepeval_suite.judge import SeamJudgeLLM

_MARKS_BY_QTYPE = {
    "mcq": 1,
    "very_short_answer": 2,
    "short_answer": 3,
    "long_answer": 5,
}
_MCQ_LABELS = ["A", "B", "C", "D"]


def build_generation_metrics(judge: SeamJudgeLLM) -> list[BaseMetric]:
    """The full suite for one scored run; judge is shared across metrics."""
    return [
        GEval(
            name="ncert_fidelity",
            evaluation_steps=[
                "The retrieval context contains the NCERT excerpts this "
                "question cites as its source.",
                "Check every factual claim in the stem, options, and answer "
                "against the retrieval context.",
                "Heavily penalize claims that contradict the context.",
                "Moderately penalize claims absent from the context even if "
                "they are true elsewhere in the textbook — citing an excerpt "
                "that does not support the fact is a grounding failure.",
                "Terminology should match NCERT usage.",
            ],
            evaluation_params=[
                SingleTurnParams.ACTUAL_OUTPUT,
                SingleTurnParams.RETRIEVAL_CONTEXT,
            ],
            model=judge,
            threshold=0.8,
        ),
        GEval(
            name="self_containedness",
            evaluation_steps=[
                "Judge whether a student who cannot see any textbook excerpt, "
                "table, or figure can fully understand and answer this "
                "question.",
                "Penalize phrasing like 'according to the passage/table/"
                "figure above'.",
                "Heavily penalize questions whose answer requires recalling "
                "data values (melting points, table constants) that are not "
                "reproduced in the question itself.",
            ],
            evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT],
            model=judge,
            threshold=0.8,
        ),
        GEval(
            name="answer_correctness",
            evaluation_steps=[
                "Verify the provided answer is correct according to the "
                "retrieval context.",
                "For MCQs, exactly the labelled option must be correct; "
                "penalize if any other option is equally defensible.",
                "For non-MCQs, the answer must be unambiguous and complete "
                "for the marks claimed.",
            ],
            evaluation_params=[
                SingleTurnParams.ACTUAL_OUTPUT,
                SingleTurnParams.RETRIEVAL_CONTEXT,
            ],
            model=judge,
            threshold=0.8,
        ),
        GEval(
            name="difficulty_plausibility",
            evaluation_steps=[
                "Assess whether this works as a CBSE Class 10 board exam "
                "item at its stated marks.",
                "Penalize items whose stem, correct option, or answer copies "
                "a sentence from the retrieval context nearly verbatim — "
                "trivially copyable items are poor discriminators.",
                "Penalize trivia recall (dates, data constants) that boards "
                "do not ask.",
                "Reward items requiring understanding or application over "
                "rote lookup.",
            ],
            evaluation_params=[
                SingleTurnParams.ACTUAL_OUTPUT,
                SingleTurnParams.RETRIEVAL_CONTEXT,
            ],
            model=judge,
            threshold=0.6,
        ),
        FaithfulnessMetric(model=judge, threshold=0.8),
        QuestionShapeMetric(),
        CitationSupportMetric(),
    ]


class QuestionShapeMetric(BaseMetric):
    """Deterministic structural conformity — never a judge's opinion.

    Encodes the generation contract from ``bank.generation``'s schema: known
    qtype, the qtype↔marks mapping, MCQ shape (four A–D options, answer is
    one of them), and non-empty citation lists on both fields.
    """

    def __init__(self, threshold: float = 1.0):
        self.threshold = threshold

    def measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        payload = (test_case.metadata or {}).get("payload") or {}
        failures = _shape_failures(payload)
        checks = 5
        self.score = (checks - min(len(failures), checks)) / checks
        self.reason = "; ".join(failures) or "all structural checks passed"
        self.success = self.score >= self.threshold
        return self.score

    async def a_measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return bool(self.success)

    @property
    def __name__(self):
        return "question_shape"


class CitationSupportMetric(BaseMetric):
    """Production's lexical citation screen as a deepeval metric.

    Same signal ``evals.scenarios.generation`` reports as
    ``citation_support`` — surfaced per test case here so lexical/judge
    disagreement is visible row by row in deepeval output.
    """

    def __init__(self, threshold: float = 1.0):
        self.threshold = threshold

    def measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        from bank.citation_support import review_candidate_citation_support

        metadata = test_case.metadata or {}
        review = review_candidate_citation_support(
            metadata.get("payload") or {},
            {"excerpts": metadata.get("manifest_excerpts") or []},
        )
        if review.supported:
            self.score = 1.0
        else:
            self.score = (
                float(review.question_supported) + float(review.answer_supported)
            ) / 2
        self.reason = (
            "; ".join(f"{i.field}:{i.code}" for i in review.issues)
            or "question and answer lexically supported by cited excerpts"
        )
        self.success = self.score >= self.threshold
        return self.score

    async def a_measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return bool(self.success)

    @property
    def __name__(self):
        return "citation_support"


def _shape_failures(payload: dict) -> list[str]:
    failures = []
    qtype = payload.get("qtype")
    if qtype not in _MARKS_BY_QTYPE:
        failures.append(f"unknown qtype {qtype!r}")
    elif payload.get("marks") != _MARKS_BY_QTYPE[qtype]:
        failures.append(
            f"marks {payload.get('marks')!r} != {_MARKS_BY_QTYPE[qtype]} "
            f"expected for {qtype}"
        )
    if not str(payload.get("raw_text") or "").strip():
        failures.append("empty raw_text")
    if qtype == "mcq":
        options = (payload.get("content") or {}).get("options") or []
        labels = [option.get("label") for option in options]
        if labels != _MCQ_LABELS:
            failures.append(f"MCQ options must be labelled A-D, got {labels}")
        if str(payload.get("answer", "")).strip().upper() not in _MCQ_LABELS:
            failures.append(f"MCQ answer {payload.get('answer')!r} is not a label")
    for field in ("question_citation_ids", "answer_citation_ids"):
        value = payload.get(field)
        if not isinstance(value, list) or not value:
            failures.append(f"{field} empty")
    return failures
