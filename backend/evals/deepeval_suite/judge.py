"""deepeval judge backed by the production model seam, metered.

deepeval defaults its LLM-as-judge to OpenAI; this wrapper routes judge calls
through the same ``make_chat_model`` seam and registry routing every other
eval call uses, so the judge is any registry model (OpenRouter today), its
tokens land on a :class:`~evals.metering.Meter`, and its spend is priced by
the same verified registry rates — no second provider stack, no unmetered
judge spend.
"""

from __future__ import annotations

from typing import Any

from deepeval.models import DeepEvalBaseLLM

from ai_services.llm import ModelPurpose
from evals.judges.base import _json_object_candidates
from evals.metering import Meter, metered_make_model, seam_env
from evals.registry import ModelSpec, cost_usd, get_model

_DEFAULT_JUDGE_MODEL = "google/gemini-3.5-flash"

# EDITOR_ASSISTANT is borrowed only as a resolution route (same rationale as
# evals.judges.seam): it is the purpose least entangled with the workflows
# under eval, and the env override fully determines provider/model.
_JUDGE_PURPOSE = ModelPurpose.EDITOR_ASSISTANT


class SeamJudgeLLM(DeepEvalBaseLLM):
    """Any registry model as a deepeval judge, built once through the seam.

    The chat model is constructed in ``__init__`` under ``seam_env`` (env
    overrides are process-wide, so resolving routing at call time would race
    under deepeval's async concurrency) and then invoked statelessly.
    """

    def __init__(self, model_eval_id: str = _DEFAULT_JUDGE_MODEL):
        self.spec: ModelSpec = get_model(model_eval_id)
        self.meter = Meter(self.spec.model)
        with seam_env(self.spec.env_overrides(_JUDGE_PURPOSE.value)):
            self._model = metered_make_model(self.meter)(_JUDGE_PURPOSE)

    def load_model(self):
        return self._model

    def generate(self, prompt: str, schema: Any = None, **kwargs) -> Any:
        response = self._model.invoke(prompt)
        return coerce_schema(_text(response), schema)

    async def a_generate(self, prompt: str, schema: Any = None, **kwargs) -> Any:
        response = await self._model.ainvoke(prompt)
        return coerce_schema(_text(response), schema)

    def get_model_name(self) -> str:
        return f"seam:{self.spec.eval_id}"

    @property
    def cost_usd(self) -> float | None:
        """Judge spend so far, priced at the registry's verified rates."""
        return cost_usd(
            self.spec,
            input_tokens=self.meter.input_tokens,
            output_tokens=self.meter.output_tokens,
            cache_read_tokens=self.meter.cache_read_tokens,
        )


def coerce_schema(text: str, schema: Any = None) -> Any:
    """Return raw text, or the first JSON object that validates as ``schema``.

    OpenRouter-routed models have no native structured-output guarantee, so
    schema enforcement is parse-and-validate: deepeval's metric prompts
    already demand JSON, and a validation failure raises so the caller's
    ``ErrorConfig`` decides whether the test case is skipped or fatal.
    """
    if schema is None:
        return text
    last_error: Exception | None = None
    for candidate in _json_object_candidates(text):
        try:
            return schema.model_validate(candidate)
        except Exception as exc:  # noqa: BLE001 — try every candidate object
            last_error = exc
    raise ValueError(
        f"Judge output did not contain JSON matching {schema.__name__}: "
        f"{last_error}"
    )


def _text(response: Any) -> str:
    content = getattr(response, "content", response)
    return content if isinstance(content, str) else str(content)
