"""deepeval-based scoring suite for the eval framework (Phase 1: generation).

deepeval replaces the single holistic seam-judge prompt with decomposed,
research-backed metrics: one G-Eval (chain-of-thought judge) per rubric
dimension, claim-level Faithfulness against the excerpts a candidate cites,
and pure-code metrics for the checks that should never be vibes-scored
(question shape, production's lexical citation screen). The paid phase,
consent gating, token metering, and the verified-price registry stay with the
existing harness — deepeval is the measurement layer, not the runner.

Import this package before anything imports ``deepeval``: the bootstrap below
must run first because deepeval's settings are validated at import time.
"""

import os

# docker-compose passes OPENROUTER_BASE_URL through even when unset, and
# deepeval's pydantic settings reject an empty string as a URL at import
# time. Fill in the canonical base URL (the same default the model seam
# uses) so importing deepeval never depends on shell configuration.
if not os.environ.get("OPENROUTER_BASE_URL"):
    os.environ["OPENROUTER_BASE_URL"] = "https://openrouter.ai/api/v1"
# deepeval bundles posthog/sentry telemetry; evals must not phone home.
os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")
# Never prompt to open the trace TUI from harness/CI runs.
os.environ.setdefault("DEEPEVAL_NO_INSPECT_PROMPT", "1")

from evals.deepeval_suite.adapter import (  # noqa: E402
    generation_test_cases,
    render_question,
)
from evals.deepeval_suite.judge import SeamJudgeLLM, coerce_schema  # noqa: E402
from evals.deepeval_suite.metrics import build_generation_metrics  # noqa: E402

__all__ = [
    "SeamJudgeLLM",
    "build_generation_metrics",
    "coerce_schema",
    "generation_test_cases",
    "render_question",
]
