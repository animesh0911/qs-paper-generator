"""Judge backend that shells out to the Claude Code CLI (``claude -p``).

The default judge: it runs on the developer's subscription, so scoring costs
no API money, and the print-mode JSON envelope is machine-parseable. Requires
an authenticated ``claude`` binary on PATH (the harness contract in the evals
README covers this).
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


class ClaudeCodeJudge:
    judge_id = "claude-code-cli"

    def __init__(
        self,
        *,
        binary: str = "claude",
        model: str | None = None,
        timeout_s: int = _DEFAULT_TIMEOUT_S,
    ):
        self.binary = binary
        self.model = model  # None = the CLI's configured default
        self.timeout_s = timeout_s

    def judge(self, request: JudgeRequest) -> JudgeVerdict:
        rubric_text, rubric_version = load_rubric(request.rubric_name)
        prompt = build_judge_prompt(request, rubric_text)
        cmd = [self.binary, "-p", prompt, "--output-format", "json"]
        if self.model:
            cmd += ["--model", self.model]
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=self.timeout_s
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            return JudgeVerdict(
                judge_id=self.judge_id,
                rubric_version=rubric_version,
                ok=False,
                error=f"claude CLI failed: {exc}",
            )
        if proc.returncode != 0:
            return JudgeVerdict(
                judge_id=self.judge_id,
                rubric_version=rubric_version,
                raw=proc.stdout,
                ok=False,
                error=f"claude CLI exit {proc.returncode}: {proc.stderr[:500]}",
            )
        # -p --output-format json emits an envelope; the model text is in
        # "result". Fall back to raw stdout if the envelope shape shifts.
        text = proc.stdout
        try:
            envelope = json.loads(proc.stdout)
            text = envelope.get("result", proc.stdout)
        except json.JSONDecodeError:
            pass
        return parse_verdict(
            text, judge_id=self.judge_id, rubric_version=rubric_version
        )
