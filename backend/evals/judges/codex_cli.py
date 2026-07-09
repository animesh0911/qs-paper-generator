"""Judge backend that shells out to the Codex CLI (``codex exec``).

Alternate agent harness so scores can be cross-checked against a judge from a
different model family (a standard LLM-judge de-biasing practice). Requires an
authenticated ``codex`` binary on PATH.

PLACEHOLDER NOTE (implementation issue): the exact non-interactive flags and
event-stream shape should be verified against the installed Codex CLI version
before first use; parsing below tolerates both plain text and JSONL output.
"""

from __future__ import annotations

import json
import subprocess

from evals.judges.base import (
    JudgeRequest,
    JudgeVerdict,
    build_judge_prompt,
    load_rubric,
    parse_verdict,
)

_DEFAULT_TIMEOUT_S = 300


class CodexCliJudge:
    judge_id = "codex-cli"

    def __init__(self, *, binary: str = "codex", timeout_s: int = _DEFAULT_TIMEOUT_S):
        self.binary = binary
        self.timeout_s = timeout_s

    def judge(self, request: JudgeRequest) -> JudgeVerdict:
        rubric_text, rubric_version = load_rubric(request.rubric_name)
        prompt = build_judge_prompt(request, rubric_text)
        cmd = [self.binary, "exec", prompt]
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=self.timeout_s
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            return JudgeVerdict(
                judge_id=self.judge_id,
                rubric_version=rubric_version,
                ok=False,
                error=f"codex CLI failed: {exc}",
            )
        if proc.returncode != 0:
            return JudgeVerdict(
                judge_id=self.judge_id,
                rubric_version=rubric_version,
                raw=proc.stdout,
                ok=False,
                error=f"codex CLI exit {proc.returncode}: {proc.stderr[:500]}",
            )
        return parse_verdict(
            _final_text(proc.stdout),
            judge_id=self.judge_id,
            rubric_version=rubric_version,
        )


def _final_text(stdout: str) -> str:
    """Collect assistant text whether stdout is plain text or JSONL events."""
    texts: list[str] = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        for key in ("text", "content", "message", "result"):
            value = event.get(key)
            if isinstance(value, str) and value:
                texts.append(value)
    return "\n".join(texts) if texts else stdout
