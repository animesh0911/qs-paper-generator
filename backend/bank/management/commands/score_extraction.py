"""score_extraction — measure an extraction JSON against a hand-built ground truth.

The deterministic (no-LLM) scorer for the extraction pipeline. Given an
``extract_paper`` output and a committed ground-truth manifest for the same
paper, it reports recall, precision, and section / qtype / structure accuracy so
prompt or model variants are compared by numbers, not vibes.

Ground-truth manifest shape (one per source paper, hand-built from the PDF)::

    {
      "source_pdf": "science_2026/31_1_1_Science.pdf",
      "total_expected": 39,
      "questions": [
        {"num": 1, "section": "A", "qtype": "mcq", "marks": 1,
         "key": "gaseous exchange"},
        ...
      ]
    }

``key`` is a short, unique phrase from the question's English stem; an extracted
question matches a ground-truth entry when the (normalised) key is a substring
of the (normalised) extracted text. Each ground-truth entry matches at most one
extracted question and vice-versa.

Usage::

    python manage.py score_extraction content/parsed/31_1_1_Science.json \\
        content/eval/31_1_1_Science.truth.json
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from bank.question_shape import compute_parse_quality


def _norm(text: str) -> str:
    """Lowercase, drop punctuation, collapse whitespace — for substring matching."""
    text = re.sub(r"\s+", " ", (text or "").lower().strip())
    return re.sub(r"[^\w\s]", "", text)


def score(extraction: dict, ground_truth: dict) -> dict:
    """Score one extraction against its ground truth. Pure — no I/O, no LLM.

    Matching: a ground-truth entry is matched by the first not-yet-claimed
    extracted question whose normalised text contains the normalised ``key``.
    Returns recall/precision plus section, qtype and structure accuracy, and the
    lists of missed (uncaptured) and spurious (captured-but-not-in-truth) rows so
    a regression can name what changed, not just move a number.
    """
    ext = extraction.get("questions", [])
    gt = ground_truth.get("questions", [])
    ext_norm = [_norm(q.get("text", "")) for q in ext]

    claimed: set[int] = set()
    pairs: list[tuple[dict, dict]] = []  # (gt_entry, ext_question)
    missed: list[dict] = []
    for g in gt:
        key = _norm(g.get("key", ""))
        match_idx = next(
            (
                i
                for i, t in enumerate(ext_norm)
                if i not in claimed and key and key in t
            ),
            None,
        )
        if match_idx is None:
            missed.append(g)
            continue
        claimed.add(match_idx)
        pairs.append((g, ext[match_idx]))

    spurious = [ext[i] for i in range(len(ext)) if i not in claimed]

    section_hits = sum(1 for g, e in pairs if g.get("section") == e.get("section"))
    qtype_hits = sum(1 for g, e in pairs if g.get("qtype") == e.get("qtype"))
    structure_ok = sum(
        1 for q in ext if compute_parse_quality(q, q.get("qtype", "")) != "broken"
    )

    n_gt = len(gt) or 1
    n_ext = len(ext) or 1
    n_pairs = len(pairs) or 1
    return {
        "expected": len(gt),
        "extracted": len(ext),
        "matched": len(pairs),
        "recall": len(pairs) / n_gt,
        "precision": len(pairs) / n_ext,
        "section_accuracy": section_hits / n_pairs,
        "qtype_accuracy": qtype_hits / n_pairs,
        "structure_usable": structure_ok / n_ext,
        "missed": missed,
        "spurious": spurious,
    }


class Command(BaseCommand):
    help = "Score an extraction JSON against a ground-truth manifest (no LLM)."

    def add_arguments(self, parser):
        parser.add_argument("extraction", type=str, help="extract_paper *.json")
        parser.add_argument("ground_truth", type=str, help="ground-truth *.json")

    def handle(self, *args, **options):
        ext_path = Path(options["extraction"])
        gt_path = Path(options["ground_truth"])
        for p in (ext_path, gt_path):
            if not p.is_file():
                raise CommandError(f"Not a file: {p}")

        result = score(
            json.loads(ext_path.read_text()), json.loads(gt_path.read_text())
        )

        self.stdout.write(
            f"expected={result['expected']} extracted={result['extracted']} "
            f"matched={result['matched']}"
        )
        self.stdout.write(
            f"recall={result['recall']:.2f} precision={result['precision']:.2f} "
            f"section_acc={result['section_accuracy']:.2f} "
            f"qtype_acc={result['qtype_accuracy']:.2f} "
            f"structure_usable={result['structure_usable']:.2f}"
        )
        if result["missed"]:
            self.stdout.write(self.style.WARNING(f"MISSED ({len(result['missed'])}):"))
            for g in result["missed"]:
                self.stdout.write(
                    f"  Q{g.get('num')} [{g.get('section')}] {g.get('key')}"
                )
        if result["spurious"]:
            self.stdout.write(
                self.style.WARNING(f"SPURIOUS ({len(result['spurious'])}):")
            )
            for q in result["spurious"]:
                self.stdout.write(
                    f"  [{q.get('section')}/{q.get('qtype')}] {q.get('text','')[:60]}"
                )
