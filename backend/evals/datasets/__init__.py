"""Datasets: truth manifests, fixtures, and scale-bundle building.

Layout convention (everything content-side lives under the mounted
``/content`` volume, next to the existing extraction eval assets):

- ``/content/eval/*.truth.json``          — hand-built extraction ground truth
  (existing ``score_extraction`` format, extended per-question with optional
  ``figures``/``equations`` fields for the fidelity metrics).
- ``/content/eval/bundles/``              — synthetic 50/500-page PDFs built by
  ``evals.datasets.build_scale_bundles`` + their merged truth manifests.
- ``/content/eval/golden/``               — hand-verified golden answers used
  to calibrate the answer judge.
- ``/content/eval/results/``              — RunRecord JSONL + reports
  (existing convention from ``benchmark_extraction --record``).
- ``evals/datasets/fixtures/``            — small, repo-committed run inputs
  (generation request fixtures, usage profiles).
"""

from pathlib import Path

CONTENT_ROOT = Path("/content")
EVAL_ROOT = CONTENT_ROOT / "eval"
BUNDLES_DIR = EVAL_ROOT / "bundles"
GOLDEN_DIR = EVAL_ROOT / "golden"
RESULTS_DIR = EVAL_ROOT / "results"
FIXTURES_DIR = Path(__file__).parent / "fixtures"
