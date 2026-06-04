"""Tests for bank.ingestor (Gemini native-PDF path).

The Ingestor coordinator is tested end-to-end with a stub Extractor — no live
Gemini call. GeminiExtractor's per-page extraction + coercion is tested against
a stub LLMClient. Pure helpers (`compute_parse_quality` from
`bank.question_shape`, `_parse_source_filename`) are tested directly.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from bank.diagram_cropper import _crop_figure, crop_to_dir
from bank.ingestor import (
    GeminiExtractor,
    Ingestor,
    _coerce_figures,
    _parse_source_filename,
)
from bank.models import Chapter, Question
from bank.question_shape import compute_parse_quality

# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


def _q(section="A", qtype="short_answer", marks=1, text="Q?", **extra):
    """Build a coordinator-shape question dict (Extractor output)."""
    base = {
        "section": section,
        "qtype": qtype,
        "marks": marks,
        "text": text,
        "options": [],
        "content": {},
        "chapter_slug": None,
        "cognitive_level": "U",
        "topic_names": [],
        "primary_form": "none",
    }
    base.update(extra)
    return base


class StubExtractor:
    """Extractor adapter returning canned, already-tagged question dicts."""

    def __init__(self, questions: list[dict]):
        self._questions = questions

    def extract(self, pdf_bytes: bytes) -> list[dict]:
        return [dict(q) for q in self._questions]


class StubCropper:
    """DiagramCropper adapter returning a fixed primary asset per row, no fitz."""

    def __init__(self, primary_assets: list[str | None]):
        self._primary_assets = primary_assets
        self.calls: list[tuple[int, int]] = []

    def crop(self, pdf_bytes, rows, fingerprints):
        self.calls.append((len(rows), len(fingerprints)))
        return list(self._primary_assets)


# ---------------------------------------------------------------------------
# Ingestor — end-to-end with a stub Extractor
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_ingestor_persists_unverified_questions_with_tags():
    """End-to-end: extractor → coordinator → DB.

    Why this matters: this is the only test that proves the coordinator wires the
    extractor output through dedup, provenance, and persist. If a step is skipped
    or the row shape drifts, this fails."""
    questions = [
        _q(section="A", qtype="mcq", chapter_slug="electricity", cognitive_level="Ap"),
        _q(
            section="B",
            text="Define inertia.",
            chapter_slug="electricity",
            cognitive_level="Ap",
        ),
    ]
    result = Ingestor(extractor=StubExtractor(questions)).ingest(b"%PDF")

    assert result.created == 2
    assert Question.objects.count() == 2
    assert all(q.verified is False for q in Question.objects.all())

    electricity = Chapter.objects.get(slug="electricity")
    assert all(q.chapter_id == electricity.pk for q in Question.objects.all())
    assert all(q.cognitive_level == "Ap" for q in Question.objects.all())


@pytest.mark.django_db
def test_ingestor_uses_injected_cropper(settings, tmp_path):
    """The DiagramCropper seam is injectable: a stub's asset reaches the row.

    Why this matters: cropping is the Ingestor's second adapter (CONTEXT.md). The
    coordinator must delegate to whatever cropper it's handed and wire that
    cropper's primary asset onto Question.diagram — provable without PyMuPDF."""
    settings.MEDIA_ROOT = str(tmp_path)
    cropper = StubCropper(["diagrams/stub-0.png"])
    Ingestor(
        extractor=StubExtractor(
            [_q(section="C", qtype="short_answer", text="Draw it.")]
        ),
        cropper=cropper,
    ).ingest(b"%PDF")

    assert cropper.calls == [(1, 1)]  # coordinator called the seam once
    row = Question.objects.get()
    assert row.diagram.name == "diagrams/stub-0.png"
    assert row.has_diagram is True


@pytest.mark.django_db
def test_ingestor_empty_pdf_creates_nothing():
    result = Ingestor(extractor=StubExtractor([])).ingest(b"")
    assert result.created == 0
    assert Question.objects.count() == 0


@pytest.mark.django_db
def test_ingestor_unknown_chapter_slug_persists_without_chapter():
    """An unknown slug → chapter stays None, ingestion still succeeds."""
    result = Ingestor(
        extractor=StubExtractor([_q(chapter_slug="no-such-chapter")])
    ).ingest(b"x")
    assert result.created == 1
    assert Question.objects.get().chapter_id is None


@pytest.mark.django_db
def test_ingestor_sets_parse_quality_from_structure():
    """Coordinator sets parse_quality structurally (no source-text verification).

    Why this matters: parse_quality is the picker gate. An mcq with no options is
    broken; a non-empty short answer is clean — both decided by structure here."""
    questions = [
        _q(section="A", qtype="mcq", text="Which gas?", options=[]),
        _q(section="C", qtype="short_answer", text="Define refraction."),
    ]
    Ingestor(extractor=StubExtractor(questions)).ingest(b"x")

    mcq = Question.objects.get(qtype="mcq")
    sa = Question.objects.get(qtype="short_answer")
    assert mcq.parse_quality == "broken"  # mcq with zero options
    assert sa.parse_quality == "clean"  # non-empty short answer


@pytest.mark.django_db
def test_ingestor_persists_content_options_and_topics():
    """Structured content, options, topic_names, primary_form reach the row."""
    q = _q(
        section="A",
        qtype="mcq",
        text="Which gas?",
        options=[{"label": "A", "text": "O2"}],
        content={"stem": [{"type": "paragraph", "text": "Which gas?"}]},
        topic_names=["Photosynthesis"],
        primary_form="diagram_based",
    )
    Ingestor(extractor=StubExtractor([q])).ingest(b"x")

    row = Question.objects.get()
    assert row.options == [{"label": "A", "text": "O2"}]
    assert row.content["stem"][0]["text"] == "Which gas?"
    assert row.topic_names == ["Photosynthesis"]
    assert row.primary_form == "diagram_based"
    assert row.has_diagram is True  # diagram_based reinforces it


# ---------------------------------------------------------------------------
# GeminiExtractor — per-page extraction + coercion, via a stub LLMClient
# ---------------------------------------------------------------------------


class SequenceLLMClient:
    """LLMClient stub: one question per call, so we can assert call count + order."""

    def __init__(self):
        self.calls: list[bytes] = []

    def extract(self, pdf_bytes, prompt, response_schema):
        self.calls.append(pdf_bytes)
        n = len(self.calls)
        return {
            "questions": [{"qtype": "short_answer", "marks": 2, "rawText": f"Q{n}"}]
        }


def test_gemini_extractor_calls_client_once_per_page_and_merges(monkeypatch):
    """One request per page; results merge in document order.

    Why this matters: per-page extraction is what gives deep reads on long
    scanned papers — the coordinator must call once per page, not once per doc."""
    monkeypatch.setattr("bank.ingestor._split_pages", lambda b: [b"p1", b"p2", b"p3"])
    client = SequenceLLMClient()
    out = GeminiExtractor(client=client).extract(b"%PDF")

    assert client.calls == [b"p1", b"p2", b"p3"]
    assert [q["text"] for q in out] == ["Q1", "Q2", "Q3"]
    # marks=2 → Section B, derived deterministically (not from the model).
    assert all(q["section"] == "B" for q in out)


class OnePageLLMClient:
    """Returns a payload on the first call, empty afterwards."""

    def __init__(self, payload: dict):
        self.payload = payload
        self.calls = 0

    def extract(self, pdf_bytes, prompt, response_schema):
        self.calls += 1
        return self.payload if self.calls == 1 else {"questions": []}


def test_gemini_extractor_coerces_question_fields():
    """rawText→text, marks/section derived, topic_names cleaned, primary_form clamped.

    Why this matters: the model's output is normalised to the row shape here; a
    garbage primary_form must be clamped, not persisted raw. Invalid PDF bytes
    can't be split, so the extractor makes one whole-document call."""
    payload = {
        "questions": [
            {
                "qtype": "mcq",
                # no marks → qtype implies 1 → Section A
                "rawText": "Which gas?",
                "options": [{"label": "A", "text": "O2"}],
                "content": {"stem": [{"type": "paragraph", "text": "Which gas?"}]},
                "chapter_slug": "electricity",
                "cognitive_level": "R",
                "topic_names": ["Photosynthesis", "  ", 7],
                "primary_form": "interpretive_dance",
            }
        ]
    }
    out = GeminiExtractor(client=OnePageLLMClient(payload)).extract(b"%PDF")

    assert len(out) == 1
    q = out[0]
    assert q["section"] == "A"  # marks 1 → A
    assert q["marks"] == 1  # qtype default (mcq → 1)
    assert q["text"] == "Which gas?"
    assert q["topic_names"] == ["Photosynthesis"]  # blanks/non-str dropped
    assert q["primary_form"] == "none"  # unknown value clamped
    assert q["chapter_slug"] == "electricity"


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("17. Which gas is released?", "Which gas is released?"),
        ("3. State the law.", "State the law."),
        # Decimals must survive — only a number + dot + whitespace is stripped.
        ("3.5 kg of water is heated.", "3.5 kg of water is heated."),
        ("No leading number here.", "No leading number here."),
    ],
)
def test_coerce_strips_leading_question_number(raw, expected):
    """A leading 'NN. ' question number is stripped from the stem, decimals kept.

    Why this matters: the model leaves question numbers on some stems; they are
    noise in the bank and would break dedup against a clean re-extract."""
    payload = {"questions": [{"qtype": "short_answer", "marks": 3, "rawText": raw}]}
    out = GeminiExtractor(client=OnePageLLMClient(payload)).extract(b"%PDF")
    assert out[0]["text"] == expected


@pytest.mark.parametrize(
    "marks,expected_section",
    [(1, "A"), (2, "B"), (3, "C"), (4, "E"), (5, "D")],
)
def test_section_derived_from_marks(marks, expected_section):
    """Section is a deterministic function of marks, not the model's guess.

    Why this matters: per-page extraction has no section header to trust, so the
    mark value is the source of truth (CBSE format: 1→A, 2→B, 3→C, 4→E, 5→D)."""
    payload = {
        "questions": [
            # The model's own "section" is deliberately wrong to prove it is ignored.
            {"section": "A", "qtype": "short_answer", "marks": marks, "rawText": "Q?"}
        ]
    }
    out = GeminiExtractor(client=OnePageLLMClient(payload)).extract(b"%PDF")
    assert out[0]["section"] == expected_section


def test_gemini_extractor_dedups_question_spanning_pages(monkeypatch):
    """A question repeated across two page calls is emitted once.

    Why this matters: a question straddling a page break is seen on both pages;
    the fingerprint dedup keeps the bank from carrying duplicates."""
    monkeypatch.setattr("bank.ingestor._split_pages", lambda b: [b"p1", b"p2"])

    class RepeatClient:
        def extract(self, pdf_bytes, prompt, response_schema):
            return {
                "questions": [
                    {
                        "qtype": "short_answer",
                        "marks": 3,
                        "rawText": "Define refraction.",
                    }
                ]
            }

    out = GeminiExtractor(client=RepeatClient()).extract(b"%PDF")
    assert len(out) == 1


def test_gemini_extractor_rewrites_figure_page_to_absolute(monkeypatch):
    """A figure localised on its single-page slice gets the absolute page number.

    Why this matters: the cropper clips from the full document, so a per-page
    figure ref of 1 must become the real page or the wrong page gets cropped."""
    monkeypatch.setattr("bank.ingestor._split_pages", lambda b: [b"p1", b"p2", b"p3"])

    class FigureOnEachPage:
        def __init__(self):
            self.n = 0

        def extract(self, pdf_bytes, prompt, response_schema):
            self.n += 1
            return {
                "questions": [
                    {
                        "qtype": "short_answer",
                        "marks": 3,
                        "rawText": f"Question {self.n}",
                        "figures": [
                            {"page": 1, "bbox": [0, 0, 1, 1], "region": "stem"}
                        ],
                    }
                ]
            }

    out = GeminiExtractor(client=FigureOnEachPage()).extract(b"%PDF")
    assert [q["figures"][0]["page"] for q in out] == [1, 2, 3]


# ---------------------------------------------------------------------------
# _compute_parse_quality — structural self-assessment
# ---------------------------------------------------------------------------


def test_compute_parse_quality_clean_assertion_reason():
    content = {
        "assertion": [{"type": "paragraph", "text": "Some assertion."}],
        "reason": [{"type": "paragraph", "text": "Some reason."}],
    }
    raw_q = {"text": "AR", "content": content}
    assert compute_parse_quality(raw_q, "assertion_reason") == "clean"


def test_compute_parse_quality_broken_when_content_empty():
    """A structured qtype with empty content is broken, not silently partial:
    parse_quality='broken' means the picker excludes the question."""
    raw_q = {"text": "Assertion (A): X", "content": {}}
    assert compute_parse_quality(raw_q, "assertion_reason") == "broken"


def test_compute_parse_quality_broken_mcq_missing_options():
    raw_q = {"text": "Which gas?", "options": [], "content": {}}
    assert compute_parse_quality(raw_q, "mcq") == "broken"


def test_compute_parse_quality_clean_mcq_four_options():
    opts = [
        {"label": label, "text": t}
        for label, t in [("A", "O2"), ("B", "CO2"), ("C", "N2"), ("D", "H2")]
    ]
    raw_q = {"text": "Which gas?", "options": opts, "content": {}}
    assert compute_parse_quality(raw_q, "mcq") == "clean"


def test_compute_parse_quality_mcq_counts_content_options_when_flat_empty():
    """An MCQ with options only in content.options is clean, not broken.

    Why this matters: the model often fills content.options (the contract source
    the renderer reads) but leaves the flat options list empty. Gating on the
    flat list alone falsely marked ~half of a real paper's MCQs broken and
    dropped them from the picker."""
    content = {
        "stem": [{"type": "paragraph", "text": "Which gas?"}],
        "options": [
            {"label": "A", "content": [{"type": "paragraph", "text": "O2"}]},
            {"label": "B", "content": [{"type": "paragraph", "text": "CO2"}]},
            {"label": "C", "content": [{"type": "paragraph", "text": "N2"}]},
            {"label": "D", "content": [{"type": "paragraph", "text": "H2"}]},
        ],
    }
    raw_q = {"text": "Which gas?", "options": [], "content": content}
    assert compute_parse_quality(raw_q, "mcq") == "clean"


def test_compute_parse_quality_mcq_broken_when_no_options_anywhere():
    """No options in flat list or content → still broken (not a false clean)."""
    raw_q = {"text": "Which gas?", "options": [], "content": {"stem": []}}
    assert compute_parse_quality(raw_q, "mcq") == "broken"


def test_compute_parse_quality_clean_short_answer_with_text():
    raw_q = {"text": "Define refraction.", "content": {}}
    assert compute_parse_quality(raw_q, "short_answer") == "clean"


# ---------------------------------------------------------------------------
# _parse_source_filename
# ---------------------------------------------------------------------------


def test_parse_source_filename_underscore_science():
    """Underscore-separated CBSE code with subject label and year from parent dir."""
    result = _parse_source_filename(Path("content/science_2024/31_1_1_Science.pdf"))
    assert result == {
        "source_type": "previous_year_paper",
        "source_name": "31-1-1 Science 2024",
        "source_file_name": "31_1_1_Science.pdf",
    }


def test_parse_source_filename_dash_only():
    result = _parse_source_filename(Path("content/science_2025/31-2-1.pdf"))
    assert result == {
        "source_type": "previous_year_paper",
        "source_name": "31-2-1 2025",
        "source_file_name": "31-2-1.pdf",
    }


def test_parse_source_filename_prefixed():
    result = _parse_source_filename(
        Path("content/science_2026/1190-1_31-4-1_Science.pdf")
    )
    assert result["source_type"] == "previous_year_paper"
    assert result["source_file_name"] == "1190-1_31-4-1_Science.pdf"
    assert "2026" in result["source_name"]
    assert "Science" in result["source_name"]


def test_parse_source_filename_no_year_in_parent():
    result = _parse_source_filename(Path("uploads/31_1_1_Science.pdf"))
    assert result["source_type"] == "previous_year_paper"
    assert result["source_name"] == "31-1-1 Science"


# ---------------------------------------------------------------------------
# Figure crops as assets (#77)
# ---------------------------------------------------------------------------


def _one_page_pdf() -> bytes:
    """A real 1-page PDF with a drawn rectangle, so cropping has pixels to grab."""
    import fitz

    doc = fitz.open()
    page = doc.new_page()  # default A4
    page.draw_rect(fitz.Rect(60, 60, 300, 300), fill=(0, 0, 0))
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def test_crop_to_dir_writes_committed_png_and_rewrites_content():
    """crop_to_dir saves a PNG beside the JSON and upgrades the placeholder.

    Why this matters: this is the offline path that makes diagrams survive a
    fresh checkout — the file must be written under assets_dir and the content's
    image_placeholder replaced by an image item referencing it by storage name
    (contract §9, no inline URL)."""
    assets_dir = Path(_tmp_assets_dir())
    q = {
        "text": "Draw the magnetic field lines around a bar magnet.",
        "content": {
            "stem": [
                {"type": "paragraph", "text": "Draw the field lines."},
                {"type": "image_placeholder", "text": "bar magnet"},
            ]
        },
        "figures": [{"page": 1, "bbox": [0.1, 0.1, 0.5, 0.5], "region": "stem"}],
    }

    crop_to_dir(_one_page_pdf(), [q], ["abcd1234ef"], assets_dir)

    pngs = list(assets_dir.glob("*.png"))
    assert [p.name for p in pngs] == ["abcd1234-0.png"]
    stem = q["content"]["stem"]
    images = [it for it in stem if it["type"] == "image"]
    assert images == [{"type": "image", "assetId": "diagrams/abcd1234-0.png"}]
    # The placeholder was upgraded in place, not left alongside the image.
    assert not any(it["type"] == "image_placeholder" for it in stem)


def _tmp_assets_dir() -> str:
    import tempfile

    return tempfile.mkdtemp()


def test_crop_figure_returns_png_for_in_range_box():
    """A valid page+box yields PNG bytes; an out-of-range page yields None.

    Why this matters: the crop must fail soft so a bad box degrades to the
    image_placeholder instead of crashing the whole ingest batch (ADR-0004)."""
    import fitz

    doc = fitz.open(stream=_one_page_pdf(), filetype="pdf")
    try:
        png = _crop_figure(doc, 1, [0.1, 0.1, 0.5, 0.5])
        assert png is not None
        # PNG magic — a real raster, not the whole page.
        assert png[:8] == b"\x89PNG\r\n\x1a\n"
        assert _crop_figure(doc, 99, [0.1, 0.1, 0.5, 0.5]) is None
    finally:
        doc.close()


@pytest.mark.django_db
def test_ingestor_crops_figure_and_references_asset(settings, tmp_path):
    """A boxed stem diagram persists a crop and is referenced by assetId, no URL.

    Why this matters: contract §9 forbids inline image URLs — the frontend
    resolves assetId to served media. If the loader emitted a `url` or skipped the
    crop, structured rendering of diagram questions would break."""
    settings.MEDIA_ROOT = str(tmp_path)
    q = _q(
        section="C",
        qtype="short_answer",
        text="Draw the magnetic field lines around a bar magnet.",
        content={
            "stem": [
                {"type": "paragraph", "text": "Draw the field lines."},
                {"type": "image_placeholder", "text": "Bar magnet field."},
            ]
        },
        figures=[{"page": 1, "bbox": [0.1, 0.1, 0.5, 0.5], "region": "stem"}],
    )
    Ingestor(extractor=StubExtractor([q])).ingest(_one_page_pdf())

    row = Question.objects.get()
    assert row.diagram  # FileField points at the primary crop
    assert row.has_diagram is True
    items = row.content["stem"]
    image_items = [it for it in items if it["type"] == "image"]
    assert len(image_items) == 1
    assert image_items[0]["assetId"]
    assert "url" not in image_items[0]
    # Placeholder was upgraded in place, not left alongside the image.
    assert not any(it["type"] == "image_placeholder" for it in items)


@pytest.mark.django_db
def test_ingestor_attaches_option_level_crop_to_right_option(settings, tmp_path):
    """An option-scoped figure lands inside that option's content, not the stem."""
    settings.MEDIA_ROOT = str(tmp_path)
    q = _q(
        section="A",
        qtype="mcq",
        text="Which circuit is correct?",
        options=[{"label": "A", "text": ""}, {"label": "B", "text": ""}],
        content={
            "stem": [{"type": "paragraph", "text": "Which circuit is correct?"}],
            "options": [
                {"label": "A", "content": [{"type": "image_placeholder", "text": "A"}]},
                {"label": "B", "content": [{"type": "image_placeholder", "text": "B"}]},
            ],
        },
        figures=[
            {"page": 1, "bbox": [0.1, 0.1, 0.4, 0.4], "region": "options", "label": "B"}
        ],
    )
    Ingestor(extractor=StubExtractor([q])).ingest(_one_page_pdf())

    row = Question.objects.get()
    opt_b = next(o for o in row.content["options"] if o["label"] == "B")
    opt_a = next(o for o in row.content["options"] if o["label"] == "A")
    assert opt_b["content"][0]["type"] == "image"
    assert opt_b["content"][0]["assetId"]
    # Option A had no figure → its placeholder is untouched.
    assert opt_a["content"][0]["type"] == "image_placeholder"


@pytest.mark.django_db
def test_ingestor_matches_option_label_case_insensitively(settings, tmp_path):
    """A figure label "b" still attaches to option "B".

    Why this matters: figure and option labels come from the model but their
    casing can drift; a strict match would silently strand the crop and leave the
    placeholder, hiding the diagram from the assembled paper."""
    settings.MEDIA_ROOT = str(tmp_path)
    q = _q(
        section="A",
        qtype="mcq",
        text="Which circuit is correct?",
        options=[{"label": "B", "text": ""}],
        content={
            "options": [
                {"label": "B", "content": [{"type": "image_placeholder", "text": "B"}]},
            ],
        },
        figures=[
            {"page": 1, "bbox": [0.1, 0.1, 0.4, 0.4], "region": "options", "label": "b"}
        ],
    )
    Ingestor(extractor=StubExtractor([q])).ingest(_one_page_pdf())

    opt_b = Question.objects.get().content["options"][0]
    assert opt_b["content"][0]["type"] == "image"
    assert opt_b["content"][0]["assetId"]


@pytest.mark.django_db
def test_ingestor_unboxable_diagram_keeps_placeholder_and_flags_has_diagram(
    settings, tmp_path
):
    """No figure box → placeholder stays and has_diagram is still True.

    Why this matters: a diagram the model could not localise must still be flagged
    so the reviewer knows a crop is missing — silently dropping has_diagram would
    hide it."""
    settings.MEDIA_ROOT = str(tmp_path)
    q = _q(
        section="C",
        qtype="short_answer",
        text="Describe the experiment.",
        content={"stem": [{"type": "image_placeholder", "text": "Apparatus diagram."}]},
        primary_form="diagram_based",
        figures=[],
    )
    Ingestor(extractor=StubExtractor([q])).ingest(_one_page_pdf())

    row = Question.objects.get()
    assert not row.diagram
    assert row.has_diagram is True
    assert row.content["stem"][0]["type"] == "image_placeholder"


@pytest.mark.django_db
def test_ingestor_bad_box_degrades_to_placeholder(settings, tmp_path):
    """An out-of-range page box fails soft: placeholder stays, no crop, no crash."""
    settings.MEDIA_ROOT = str(tmp_path)
    q = _q(
        section="C",
        qtype="short_answer",
        text="Draw the ray diagram.",
        content={"stem": [{"type": "image_placeholder", "text": "Ray diagram."}]},
        figures=[{"page": 99, "bbox": [0.1, 0.1, 0.5, 0.5], "region": "stem"}],
    )
    Ingestor(extractor=StubExtractor([q])).ingest(_one_page_pdf())

    row = Question.objects.get()
    assert not row.diagram
    assert row.content["stem"][0]["type"] == "image_placeholder"
    assert row.has_diagram is True  # placeholder still present


def test_coerce_figures_drops_malformed_entries():
    """Only well-formed boxes survive; bad page/bbox/region are dropped silently."""
    figures = _coerce_figures(
        [
            {"page": 1, "bbox": [0.1, 0.1, 0.5, 0.5], "region": "stem"},  # keep
            {"page": 0, "bbox": [0.1, 0.1, 0.5, 0.5], "region": "stem"},  # page < 1
            {"page": 1, "bbox": [0.1, 0.1, 0.5], "region": "stem"},  # bbox len != 4
            {"page": 1, "bbox": [0.5, 0.5, 0.1, 0.1], "region": "stem"},  # x0>=x1
            {"page": 1, "bbox": [0.1, 0.1, 0.5, 0.5], "region": "nope"},  # bad region
            {"page": 1, "bbox": [0.1, 0.1, 0.5, 0.5]},  # missing region
            "not-a-dict",
        ]
    )
    assert figures == [{"page": 1, "bbox": [0.1, 0.1, 0.5, 0.5], "region": "stem"}]


def test_coerce_figures_clamps_and_keeps_label_caption():
    figures = _coerce_figures(
        [
            {
                "page": 2,
                "bbox": [-0.2, 0.0, 1.5, 0.6],  # clamps to [0, 0, 1, 0.6]
                "region": "options",
                "label": " B ",
                "caption": " Circuit ",
            }
        ]
    )
    assert figures == [
        {
            "page": 2,
            "bbox": [0.0, 0.0, 1.0, 0.6],
            "region": "options",
            "label": "B",
            "caption": "Circuit",
        }
    ]
