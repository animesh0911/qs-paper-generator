"""Judge protocol, prompt assembly, and verdict parsing shared by backends.

A judge grades one payload against one versioned rubric, optionally grounded
in reference context (NCERT excerpts, a rendered PDF page description, a
golden answer). The verdict is strict JSON so downstream aggregation is
deterministic; parsing tolerates prose around the JSON but never invents
scores.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

RUBRICS_DIR = Path(__file__).parent / "rubrics"

_VERSION_RE = re.compile(r"^rubric_version:\s*(\S+)", re.MULTILINE)


def load_rubric(name: str) -> tuple[str, str]:
    """Return (rubric_text, rubric_version) for ``rubrics/<name>.md``.

    Every rubric file must declare ``rubric_version: vN`` in its header —
    verdicts carry it so a rubric edit invalidates comparability loudly.
    """
    path = RUBRICS_DIR / f"{name}.md"
    text = path.read_text(encoding="utf-8")
    match = _VERSION_RE.search(text)
    if not match:
        raise ValueError(f"Rubric {path} missing a 'rubric_version:' header line.")
    return text, match.group(1)


@dataclass(frozen=True)
class JudgeRequest:
    """One grading task: rubric + payload under test + grounding context."""

    rubric_name: str  # file stem under rubrics/
    payload: dict[str, Any]  # the thing being graded (question/answer/page)
    context: str = ""  # grounding, e.g. NCERT excerpts (may be empty)
    context_kind: str = ""  # "ncert_excerpts" | "page_text" | "golden" | ""


@dataclass
class JudgeVerdict:
    """Parsed judge output; ``ok=False`` verdicts are counted, never scored."""

    scores: dict[str, float] = field(default_factory=dict)
    rationale: str = ""
    flags: list[str] = field(default_factory=list)  # e.g. ["ungrounded_claim"]
    judge_id: str = ""
    rubric_version: str = ""
    raw: str = ""
    ok: bool = True
    error: str = ""


class Judge(Protocol):
    judge_id: str

    def judge(self, request: JudgeRequest) -> JudgeVerdict: ...


def build_judge_prompt(request: JudgeRequest, rubric_text: str) -> str:
    """Assemble the grading prompt all backends share.

    Context (when present) is authoritative: rubrics instruct the judge to
    treat the supplied reference text as ground truth and its own prior
    knowledge as secondary — that is what makes textbook-grounded grading
    meaningful.
    """
    parts = [
        "You are a strict, consistent grader for a CBSE Class 10 Science "
        "question-paper product. Grade the payload against the rubric below.",
        rubric_text,
    ]
    if request.context:
        parts.append(
            f"REFERENCE CONTEXT ({request.context_kind or 'reference'}) — treat "
            "this as ground truth; flag payload claims it does not support:\n"
            f"{request.context}"
        )
    parts.append(
        "PAYLOAD TO GRADE:\n" + json.dumps(request.payload, ensure_ascii=False)
    )
    parts.append(
        "Respond with ONLY one JSON object, no markdown fences, shaped as:\n"
        '{"scores": {"<dimension>": <0-5 number per rubric dimension>}, '
        '"flags": ["<short_snake_case_flag>", ...], '
        '"rationale": "<2-4 sentences citing the reference context>"}'
    )
    return "\n\n".join(parts)


def parse_verdict(raw_text: str, *, judge_id: str, rubric_version: str) -> JudgeVerdict:
    """Extract the verdict JSON object from possibly-noisy judge output."""
    for candidate in _json_object_candidates(raw_text):
        if isinstance(candidate, dict) and isinstance(candidate.get("scores"), dict):
            scores: dict[str, float] = {}
            for key, value in candidate["scores"].items():
                try:
                    scores[str(key)] = float(value)
                except (TypeError, ValueError):
                    continue
            return JudgeVerdict(
                scores=scores,
                rationale=str(candidate.get("rationale", "")),
                flags=[str(f) for f in candidate.get("flags") or []],
                judge_id=judge_id,
                rubric_version=rubric_version,
                raw=raw_text,
            )
    return JudgeVerdict(
        judge_id=judge_id,
        rubric_version=rubric_version,
        raw=raw_text,
        ok=False,
        error="No parseable {'scores': ...} JSON object in judge output.",
    )


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
