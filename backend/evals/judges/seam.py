"""Judge backend on a pinned API model via the production model seam.

For unattended/CI scoring where no agent CLI is authenticated. Routing reuses
``make_chat_model`` + env overrides (the same mechanism eval runs use for
candidates), so no provider plumbing is duplicated here. The judge model must
be pinned deliberately — never the model under test.
"""

from __future__ import annotations

from evals.judges.base import (
    JudgeRequest,
    JudgeVerdict,
    build_judge_prompt,
    load_rubric,
    parse_verdict,
)
from evals.metering import seam_env
from evals.registry import get_model

_DEFAULT_JUDGE_MODEL = "google/gemini-3.5-flash"


class SeamJudge:
    def __init__(self, *, model_eval_id: str = _DEFAULT_JUDGE_MODEL):
        self.spec = get_model(model_eval_id)
        self.judge_id = f"seam:{model_eval_id}"

    def judge(self, request: JudgeRequest) -> JudgeVerdict:
        from ai_services.llm import ModelPurpose, make_chat_model

        rubric_text, rubric_version = load_rubric(request.rubric_name)
        prompt = build_judge_prompt(request, rubric_text)
        # EDITOR_ASSISTANT is borrowed only as a resolution route: it is the
        # purpose least entangled with the three workflows under eval, and the
        # env override below fully determines provider/model for this call.
        purpose = ModelPurpose.EDITOR_ASSISTANT
        try:
            with seam_env(self.spec.env_overrides(purpose.value)):
                response = make_chat_model(purpose).invoke(prompt)
        except Exception as exc:  # noqa: BLE001 — a judge failure is a datum
            return JudgeVerdict(
                judge_id=self.judge_id,
                rubric_version=rubric_version,
                ok=False,
                error=f"seam judge call failed: {exc}",
            )
        text = (
            response.content
            if isinstance(response.content, str)
            else str(response.content)
        )
        return parse_verdict(
            text, judge_id=self.judge_id, rubric_version=rubric_version
        )
