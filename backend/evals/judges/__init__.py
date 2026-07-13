"""Versioned rubric definitions for judged evaluation.

The rubric markdown files under ``rubrics/`` are the source of truth for
what each judged dimension means; the deepeval suite's G-Eval evaluation
steps mirror them, and golden sets stamp ``rubric_version`` from them so a
rubric edit invalidates comparability loudly. The pre-deepeval judge
backends (claude/codex CLI, seam) were removed once ``deepeval-score``
became the single judged scoring path — see evals/README.md.
"""

from evals.judges.base import load_rubric

__all__ = ["load_rubric"]
