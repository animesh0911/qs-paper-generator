"""Rubric loading and JSON extraction shared by the eval suite.

Two survivors of the pre-deepeval judge lane, each with a live caller:
``load_rubric`` stamps rubric versions into golden sets (``evals.golden``),
and ``_json_object_candidates`` powers schema coercion for the deepeval seam
judge (``evals.deepeval_suite.judge``).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

RUBRICS_DIR = Path(__file__).parent / "rubrics"

_VERSION_RE = re.compile(r"^rubric_version:\s*(\S+)", re.MULTILINE)


def load_rubric(name: str) -> tuple[str, str]:
    """Return (rubric_text, rubric_version) for ``rubrics/<name>.md``.

    Every rubric file must declare ``rubric_version: vN`` in its header —
    golden sets carry it so a rubric edit invalidates comparability loudly.
    """
    path = RUBRICS_DIR / f"{name}.md"
    text = path.read_text(encoding="utf-8")
    match = _VERSION_RE.search(text)
    if not match:
        raise ValueError(f"Rubric {path} missing a 'rubric_version:' header line.")
    return text, match.group(1)


def _json_object_candidates(text: str):
    """Yield parsed JSON objects found in ``text``, outermost-first."""
    try:
        yield json.loads(text)
    except (json.JSONDecodeError, ValueError):
        pass
    decoder = json.JSONDecoder()
    for start in (m.start() for m in re.finditer(r"\{", text)):
        try:
            obj, _ = decoder.raw_decode(text, start)
        except (json.JSONDecodeError, ValueError):
            continue
        yield obj
