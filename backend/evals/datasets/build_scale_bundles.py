"""Build synthetic 50/500-page PDF bundles for the extraction scale runs.

Real CBSE papers are ~15–30 pages; the eval brief's 50/500-page runs need
synthetic inputs. This builder concatenates real papers from
``/content/science_202x`` into one bundle PDF per target size and writes a
provenance manifest (which source PDF supplied which page range), so scoring
can attribute extracted questions back to source papers.

Run (inside the web container)::

    python -m evals.datasets.build_scale_bundles --pages 50 500

PLACEHOLDER (implementation issue "extraction scale dataset"):
- Merged ground truth. Same-series CBSE sets (31-1-1 vs 31-1-2) share
  questions, so naively unioning truth manifests would double-match keys.
  The scorer must be segment-aware: score each source paper's truth manifest
  only against questions extracted from that paper's page range (provenance
  manifest + per-page payload order make this possible). Until that lands,
  bundles measure cost/latency at scale for real, while accuracy at scale is
  reported only for truth-covered segments.
- Source selection currently takes every readable paper PDF alphabetically;
  the issue should pin an explicit, committed source list for stability.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from evals.datasets import BUNDLES_DIR, CONTENT_ROOT

_SOURCE_GLOBS = ("science_2024/*.pdf", "science_2025/*.pdf", "science_2026/*.pdf")


def source_pdfs(root: Path = CONTENT_ROOT) -> list[Path]:
    paths: list[Path] = []
    for pattern in _SOURCE_GLOBS:
        paths.extend(sorted(root.glob(pattern)))
    if not paths:
        raise FileNotFoundError(f"No source paper PDFs under {root}/science_202x/.")
    return paths


def build_bundle(target_pages: int, out_dir: Path = BUNDLES_DIR) -> Path:
    """Concatenate real papers (cycling if needed) into one ~target-page PDF.

    Stops at the first paper boundary at/after ``target_pages`` — bundles are
    slightly over rather than cutting a paper mid-question, so extraction
    never sees a half question the truth manifest expects whole.
    """
    import fitz  # pymupdf — already a backend dependency

    out_dir.mkdir(parents=True, exist_ok=True)
    bundle = fitz.open()
    provenance: list[dict] = []
    sources = source_pdfs()
    index = 0
    while bundle.page_count < target_pages:
        source = sources[index % len(sources)]
        with fitz.open(source) as doc:
            start = bundle.page_count
            bundle.insert_pdf(doc)
            provenance.append(
                {
                    "source_pdf": str(source.relative_to(CONTENT_ROOT)),
                    "page_start": start,
                    "page_end": bundle.page_count - 1,
                    "pass": index // len(sources),  # >0 = repeated source
                }
            )
        index += 1

    out_pdf = out_dir / f"bundle_{target_pages}p.pdf"
    bundle.save(out_pdf)
    bundle.close()
    (out_dir / f"bundle_{target_pages}p.provenance.json").write_text(
        json.dumps({"target_pages": target_pages, "segments": provenance}, indent=2)
        + "\n",
        encoding="utf-8",
    )
    return out_pdf


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pages", type=int, nargs="+", default=[50, 500])
    parser.add_argument("--out", type=Path, default=BUNDLES_DIR)
    args = parser.parse_args()
    for target in args.pages:
        path = build_bundle(target, args.out)
        print(f"built {path}")


if __name__ == "__main__":
    main()
