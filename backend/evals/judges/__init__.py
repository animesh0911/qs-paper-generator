"""Pluggable LLM judges for rubric-based accuracy scoring.

The judge is deliberately *not* the model under test and *not* the production
seam default: accuracy grading must stay independent of the candidates it
ranks. Three interchangeable backends implement the same
:class:`~evals.judges.base.Judge` protocol:

- ``claude_code`` — ``claude -p`` subprocess (default; subscription-covered,
  so scoring costs no API money).
- ``codex_cli`` — ``codex exec`` subprocess (alternate agent harness).
- ``seam`` — a pinned API model through LangChain for unattended/CI runs.

Rubrics are versioned markdown files in ``rubrics/``; the rubric version is
stamped into every verdict so scores from different rubric revisions are never
silently mixed.
"""

from evals.judges.base import Judge, JudgeRequest, JudgeVerdict, load_rubric

__all__ = ["Judge", "JudgeRequest", "JudgeVerdict", "load_rubric", "get_judge"]


def get_judge(name: str, **kwargs) -> Judge:
    """Build a judge backend by CLI name (lazy imports keep deps optional)."""
    if name == "claude":
        from evals.judges.claude_code import ClaudeCodeJudge

        return ClaudeCodeJudge(**kwargs)
    if name == "codex":
        from evals.judges.codex_cli import CodexCliJudge

        return CodexCliJudge(**kwargs)
    if name == "seam":
        from evals.judges.seam import SeamJudge

        return SeamJudge(**kwargs)
    raise ValueError(f"Unknown judge {name!r}; known: claude, codex, seam.")
