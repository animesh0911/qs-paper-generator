"""Scenario 2 — PDF extraction (OCR + structuring).

Production paths under test (both already behind injection seams):

- ``native_pdf`` — ``bank.extraction.SeamExtractor.extract`` (one paid model
  call per page; the same method the extraction graph's node loop drives).
- ``ocr_mistral`` — ``bank.ocr_extractor.MistralOcrMarkdownExtractor.extract``
  (Mistral OCR per page → one structuring call per page batch).
- ``docling_guardrail`` — the brief's "docling + deterministic + free" arm:
  no LLM at all; page count + text-layer stats that gate paid runs (page
  caps as a premium lever) and quantify what a free pre-flight can catch.

Brief mapping:
- one run = one document (real paper, or a 50/500-page synthetic bundle from
  ``evals.datasets.build_scale_bundles``); batch_size = pages.
- cost splits into ocr_cost (metered pages × $/page) + llm_cost (metered
  tokens × rates) so the brief's "OCR cost per run vs LLM cost per run on OCR
  output" is answered directly from one RunRecord.
- accuracy — deterministic: the existing ``score_extraction.score`` (recall/
  precision/section/qtype/structure) against truth manifests; judge (rubric
  ``extraction_fidelity``): text/equation/diagram fidelity vs the source page.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Any

from evals.budget import UnitEstimate
from evals.judges.base import Judge, JudgeRequest
from evals.metering import Meter, metered_make_model, seam_env
from evals.records import RunRecord
from evals.registry import get_model
from evals.scenarios.base import (
    EvalNotImplemented,
    EvalUnit,
    load_artifact,
    new_record,
    save_artifact,
    settle_record,
    unit_wall,
)

SCENARIO = "extraction"
ARMS = ("native_pdf", "ocr_mistral", "docling_guardrail")

# Rough per-page token priors for the budget gate (a CBSE page is dense,
# bilingual, schema-constrained). Refined by the first recorded runs.
_EST_INPUT_TOKENS_PER_PAGE = 3_000
_EST_OUTPUT_TOKENS_PER_PAGE = 1_200


def build_units(args: argparse.Namespace) -> list[EvalUnit]:
    units = []
    for dataset in args.datasets:
        for arm in args.arms:
            models = args.models if arm != "docling_guardrail" else ["none"]
            for model_id in models:
                for trial in range(args.trials):
                    units.append(
                        EvalUnit(
                            scenario=SCENARIO,
                            arm=arm,
                            model_eval_id=model_id,
                            config={"dataset": dataset},
                            trial=trial,
                        )
                    )
    return units


def estimate(unit: EvalUnit) -> UnitEstimate:
    if unit.arm == "docling_guardrail":
        return UnitEstimate(
            unit.label, calls=0, input_tokens_per_call=0, output_tokens_per_call=0
        )
    pages = _dataset_pages(unit.config["dataset"])
    return UnitEstimate(
        label=unit.label,
        calls=pages,
        input_tokens_per_call=_EST_INPUT_TOKENS_PER_PAGE,
        output_tokens_per_call=_EST_OUTPUT_TOKENS_PER_PAGE,
        ocr_pages=pages if unit.arm == "ocr_mistral" else 0,
    )


# ---------------------------------------------------------------------------
# Paid phase
# ---------------------------------------------------------------------------


def run_unit(unit: EvalUnit) -> RunRecord:
    from bank.extraction import count_pages

    pdf_path = _dataset_pdf(unit.config["dataset"])
    pdf_bytes = pdf_path.read_bytes()
    pages = count_pages(pdf_bytes)

    if unit.arm == "docling_guardrail":
        return _run_docling_guardrail(unit, pdf_path, pdf_bytes, pages)

    spec = get_model(unit.model_eval_id)
    record = new_record(unit, spec)
    record.batch_size = pages
    meter = Meter(spec.model)

    with unit_wall(record):
        with seam_env(spec.env_overrides("extraction")):
            if unit.arm == "native_pdf":
                from bank.extraction import SeamExtractor

                questions = SeamExtractor(make_model=metered_make_model(meter)).extract(
                    pdf_bytes
                )
            elif unit.arm == "ocr_mistral":
                from ai_services.llm import ModelPurpose
                from bank.ocr_extractor import MistralOcrMarkdownExtractor

                extractor = MistralOcrMarkdownExtractor(
                    ocr_client=_MeteredOcrClient(meter),
                    chat_model=metered_make_model(meter)(ModelPurpose.EXTRACTION),
                )
                questions = extractor.extract(pdf_bytes)
            else:
                raise ValueError(f"Unknown extraction arm {unit.arm!r}")

    record.delivered = len(questions)
    save_artifact(
        record,
        {
            "dataset": unit.config["dataset"],
            "pdf": str(pdf_path),
            "pages": pages,
            "questions": questions,
        },
    )
    record.success = True
    return settle_record(record, meter, spec)


def _run_docling_guardrail(
    unit: EvalUnit, pdf_path: Path, pdf_bytes: bytes, pages: int
) -> RunRecord:
    """Free deterministic pre-flight: what can we know before paying?

    PLACEHOLDER (issue: "extraction eval — docling guardrail arm"): today this
    records page count + native-text-layer stats via pymupdf (already free and
    deterministic). The issue adds the docling parse (layout/figure detection,
    per-page text richness) and defines the guardrail policy it feeds — e.g.
    "reject > N pages", "route text-layer PDFs to a cheaper arm" — so the
    premium page-cap lever is grounded in measured numbers.
    """
    import fitz

    from evals.registry import ModelSpec

    # A pseudo-spec so the record row carries an honest "no model" identity.
    spec = ModelSpec(
        eval_id="none",
        provider="none",
        model="none",
        usd_per_1m_input=0.0,
        usd_per_1m_output=0.0,
        pricing_verified=True,
    )
    record = new_record(unit, spec)
    record.batch_size = pages
    meter = Meter("docling")

    with unit_wall(record):
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            text_chars = [len(page.get_text()) for page in doc]
        guardrail = {
            "pages": pages,
            "pages_with_text_layer": sum(1 for c in text_chars if c > 50),
            "mean_text_chars_per_page": (
                sum(text_chars) / len(text_chars) if text_chars else 0.0
            ),
        }

    record.delivered = pages
    save_artifact(
        record,
        {
            "dataset": unit.config["dataset"],
            "pdf": str(pdf_path),
            "guardrail": guardrail,
        },
    )
    record.success = True
    return settle_record(record, meter, spec)


class _MeteredOcrClient:
    """Wraps the production ``MistralOcrClient`` to meter pages + latency."""

    def __init__(self, meter: Meter):
        from bank.ocr_extractor import MistralOcrClient

        self._inner = MistralOcrClient()
        self._meter = meter

    def markdown_for_pdf(self, page_bytes: bytes) -> str:
        started = time.monotonic()
        result = self._inner.markdown_for_pdf(page_bytes)
        self._meter.record_ocr(
            pages=1,
            latency_ms=int((time.monotonic() - started) * 1000),
            model="mistral-ocr",
        )
        return result

    def process_pdf(self, pdf_bytes: bytes) -> dict:
        """PLACEHOLDER (issue: "extraction eval — OCR batch arm"): the whole-
        PDF OCR-batch graph path meters pages from the OCR response; wire when
        that arm joins the matrix."""
        raise EvalNotImplemented(
            "OCR-batch graph arm not wired yet (issue: extraction eval)."
        )

    def __getattr__(self, name: str):
        return getattr(self._inner, name)


# ---------------------------------------------------------------------------
# Scoring phase
# ---------------------------------------------------------------------------


def score_unit(
    record: dict, judge: Judge | None, *, judge_sample: int = 8
) -> dict[str, Any]:
    """Deterministic truth-manifest scoring + judged page fidelity."""
    artifact = load_artifact(record)
    accuracy: dict[str, Any] = {}

    if record.get("arm") == "docling_guardrail":
        return {"guardrail": artifact.get("guardrail", {})}

    dataset = str(record.get("config", {}).get("dataset", ""))
    if dataset.startswith("paper:"):
        # Reuse the existing deterministic scorer — the same numbers
        # `benchmark_extraction` reports, so results stay comparable with the
        # committed baselines in content/eval/results/.
        from bank.management.commands.score_extraction import score
        from evals.datasets import EVAL_ROOT
        from evals.datasets.loaders import load_truth_manifest

        truth = load_truth_manifest(
            EVAL_ROOT / f"{dataset.removeprefix('paper:')}.truth.json"
        )
        result = score({"questions": artifact["questions"]}, truth)
        accuracy["deterministic"] = {
            key: result[key]
            for key in (
                "expected",
                "extracted",
                "matched",
                "recall",
                "precision",
                "section_accuracy",
                "qtype_accuracy",
                "structure_usable",
            )
        }
        accuracy["equation_fidelity_det"] = _equation_fidelity(
            truth, artifact["questions"]
        )
    elif dataset.startswith("bundle:"):
        raise EvalNotImplemented(
            "Segment-aware bundle scoring lands with the scale-dataset issue "
            "(see evals/datasets/build_scale_bundles.py docstring); bundle "
            "runs currently report cost/latency only."
        )

    if judge is not None:
        accuracy["judge"] = _judge_fidelity(record, artifact, judge, judge_sample)
    return accuracy


def _equation_fidelity(truth: dict, questions: list[dict]) -> float | None:
    """Share of truth-manifest ``equations`` strings surviving verbatim.

    Uses the optional fidelity extension of the truth format (see
    ``evals.datasets.loaders.load_truth_manifest``); None when the manifest
    has no equation annotations yet.
    """
    expected = [
        equation
        for question in truth.get("questions", [])
        for equation in question.get("equations", [])
    ]
    if not expected:
        return None
    haystack = " ".join(
        " ".join(str(v) for v in question.values() if isinstance(v, str))
        for question in questions
    )
    return sum(1 for equation in expected if equation in haystack) / len(expected)


def _judge_fidelity(
    record: dict, artifact: dict, judge: Judge, sample: int
) -> dict[str, Any]:
    """Judge extracted questions against source-page text.

    PLACEHOLDER (issue: "extraction eval — judge fidelity"): v1 gives the
    judge the PDF's native text layer as coarse whole-document context. The
    issue upgrades this to per-page attribution (provenance from per-page
    payload order) and page-image rendering for scanned papers, where the
    text layer is empty and OCR text must stand in as the reference.
    """
    import fitz

    from evals.scenarios.generation import summarise_verdicts

    pdf_path = Path(artifact.get("pdf", ""))
    if not pdf_path.is_file():
        raise FileNotFoundError(f"Source PDF for fidelity judging: {pdf_path}")
    with fitz.open(pdf_path) as doc:
        page_text = "\n".join(page.get_text() for page in doc)

    verdicts = [
        judge.judge(
            JudgeRequest(
                rubric_name="extraction_fidelity",
                payload=question,
                context=page_text[:20_000],
                context_kind="page_text",
            )
        )
        for question in artifact.get("questions", [])[:sample]
    ]
    return summarise_verdicts(verdicts)


# ---------------------------------------------------------------------------
# Dataset resolution
# ---------------------------------------------------------------------------


def _dataset_pdf(dataset: str) -> Path:
    """``paper:<stem>`` (truth-manifest paper) or ``bundle:<pages>``."""
    from evals.datasets import BUNDLES_DIR, EVAL_ROOT
    from evals.datasets.loaders import load_truth_manifest, resolve_source_pdf

    kind, _, name = dataset.partition(":")
    if kind == "paper":
        return resolve_source_pdf(load_truth_manifest(EVAL_ROOT / f"{name}.truth.json"))
    if kind == "bundle":
        path = BUNDLES_DIR / f"bundle_{name}p.pdf"
        if not path.is_file():
            raise EvalNotImplemented(
                f"Bundle {path} not built; run "
                f"`python -m evals.datasets.build_scale_bundles --pages {name}`."
            )
        return path
    raise ValueError(f"Dataset must be paper:<stem> or bundle:<pages>, got {dataset!r}")


def _dataset_pages(dataset: str) -> int:
    from bank.extraction import count_pages

    return count_pages(_dataset_pdf(dataset).read_bytes())
