"""Dataset loading, validation, and textbook-context helpers.

Two responsibilities:

- load/validate the inputs each scenario consumes (truth manifests, PDFs,
  generation fixtures) with loud errors listing exactly what is missing —
  the "define all inputs" contract of this framework;
- fetch NCERT textbook context through the *production* corpus retrieval
  layer for grounded judging (the answers scenario) and record corpus
  coverage so ungrounded verdicts are never silently mixed with grounded ones.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from evals.datasets import EVAL_ROOT, FIXTURES_DIR


class DatasetError(RuntimeError):
    """A required eval input is missing or malformed; message says which."""


# ---------------------------------------------------------------------------
# Extraction truth manifests (score_extraction format, optionally extended)
# ---------------------------------------------------------------------------


def load_truth_manifest(path: Path) -> dict:
    """Load one ``*.truth.json``; validate the fields the scorers rely on.

    Base format is the existing ``score_extraction`` manifest. The fidelity
    extension (optional, per question) adds::

        "figures": 1,          # expected count of figure attachments
        "equations": ["CaCO3 -> CaO + CO2"]   # must survive extraction verbatim

    Manifests without the extension still score recall/precision; fidelity
    metrics then come only from the judge arm.
    """
    if not path.is_file():
        raise DatasetError(f"Truth manifest not found: {path}")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    for field in ("source_pdf", "total_expected", "questions"):
        if field not in manifest:
            raise DatasetError(f"{path} missing required field {field!r}.")
    for i, question in enumerate(manifest["questions"]):
        for field in ("num", "section", "qtype", "marks", "key"):
            if field not in question:
                raise DatasetError(f"{path} questions[{i}] missing {field!r}.")
    return manifest


def truth_manifests() -> list[tuple[str, dict]]:
    """All committed truth manifests as (paper_stem, manifest)."""
    pairs = []
    for path in sorted(EVAL_ROOT.glob("*.truth.json")):
        manifest = load_truth_manifest(path)
        pairs.append((Path(manifest["source_pdf"]).stem, manifest))
    return pairs


def resolve_source_pdf(manifest: dict) -> Path:
    """Locate the PDF a manifest refers to (paths are /content-relative)."""
    from evals.datasets import CONTENT_ROOT

    path = CONTENT_ROOT / manifest["source_pdf"]
    if not path.is_file():
        raise DatasetError(
            f"Source PDF {path} not found (manifest says {manifest['source_pdf']!r})."
        )
    return path


# ---------------------------------------------------------------------------
# Generation fixtures
# ---------------------------------------------------------------------------


def load_generation_fixtures() -> list[dict]:
    """Load the committed generation request fixtures.

    Each fixture pins one grounded generation configuration (chapter, topic
    node ids); batch size and model come from the CLI so one fixture serves
    the whole matrix.
    """
    path = FIXTURES_DIR / "generation_requests.json"
    fixtures = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(fixtures, list) or not fixtures:
        raise DatasetError(f"{path} must be a non-empty JSON list.")
    for i, fixture in enumerate(fixtures):
        for field in ("fixture_id", "chapter_slug", "chapter_map_node_ids"):
            if field not in fixture:
                raise DatasetError(f"{path}[{i}] missing {field!r}.")
    return fixtures


def load_usage_profiles() -> dict:
    """Usage profiles for the per-user/month cost roll-up (see report.py)."""
    path = FIXTURES_DIR / "usage_profiles.json"
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Textbook grounding for judges (production corpus retrieval)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CorpusCoverage:
    """Which requested chapters the seeded corpus can actually ground."""

    covered_slugs: tuple[str, ...]
    missing_slugs: tuple[str, ...]

    @property
    def fraction(self) -> float:
        total = len(self.covered_slugs) + len(self.missing_slugs)
        return len(self.covered_slugs) / total if total else 0.0


def corpus_coverage(chapter_slugs: list[str]) -> CorpusCoverage:
    """Report which chapters have retrievable textbook chunks.

    Today only jesc104/jesc110 are imported; the answers rubric handles the
    uncovered case explicitly (``no_textbook_context``), and expanding
    coverage is a tracked implementation issue.
    """
    from corpus.models import RetrievalChunk

    covered, missing = [], []
    for slug in dict.fromkeys(chapter_slugs):
        exists = RetrievalChunk.objects.filter(chapter__slug=slug).exists()
        (covered if exists else missing).append(slug)
    return CorpusCoverage(tuple(covered), tuple(missing))


def textbook_context_for_question(question) -> str:
    """Retrieve NCERT excerpts for one ``bank.models.Question`` via the
    production retriever; empty string when the chapter is not in the corpus.

    PLACEHOLDER (implementation issue "answers eval"): retrieval currently
    keys on the chapter's full chunk set via search; tuning (query text from
    question stem, limit, content types) belongs to the issue, as does an
    excerpt-length cap consistent with the judge's context budget.
    """
    from corpus.retrieval import PostgresTextbookRetriever, TextbookRetrievalRequest

    if question.chapter is None:
        return ""
    context = PostgresTextbookRetriever().retrieve(
        TextbookRetrievalRequest(
            chapter=question.chapter,
            query_text=question.text[:500],
            limit=5,
        )
    )
    return "\n\n".join(result.chunk.text for result in context.results)
