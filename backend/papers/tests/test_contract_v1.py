"""Contract compliance tests for paper_document.v1 (issue #46 — Phase 8 verify).

Assembles a paper via the API and validates the response against every required
field in contracts/v1_contract.md. The ``document`` fixture is parametrized over
two banks — a synthetic ``seeded_bank`` (fast, exact slot coverage) and the real
committed corpus loaded from ``content/parsed/`` via ``load_questions`` — so
every assertion in this module guards both the synthetic and the real path
(issue #135).
"""

from __future__ import annotations

import pytest
from django.core.management import call_command
from rest_framework import status

# Legacy field names that must NOT appear in any paper_document.v1 response.
# These were renamed in the paper_document.v1 contract rewrite.
_BANNED_KEYS = frozenset(
    [
        "requestId",
        "templateId",
        "templateName",
        "paperId",
        "headerBlocks",
        "slotId",
        "displayNumber",
        "questionType",
        "sourceType",
        "sourceName",
    ]
)


def _all_keys(obj) -> set[str]:
    """Recursively collect every dict key in a nested structure."""
    keys: set[str] = set()
    if isinstance(obj, dict):
        keys.update(obj.keys())
        for v in obj.values():
            keys |= _all_keys(v)
    elif isinstance(obj, list):
        for item in obj:
            keys |= _all_keys(item)
    return keys


@pytest.fixture
def loaded_bank(db, tmp_path, settings):
    """Load the committed 2026 corpus (content/parsed/) into the bank.

    Rehydrates assets into a throwaway MEDIA_ROOT — same isolation as
    test_load_questions.test_rehydrates_committed_assets_into_storage — so the
    run doesn't write crops into the developer's real backend/media/diagrams/.
    """
    settings.MEDIA_ROOT = str(tmp_path / "media")
    parsed_dir = settings.BASE_DIR.parent / "content" / "parsed"
    call_command("load_questions", str(parsed_dir))


@pytest.fixture(params=["seeded_bank", "loaded_bank"])
def document(request, api_client):
    """A document assembled against each bank in turn (contract guards both)."""
    request.getfixturevalue(request.param)
    resp = api_client.post("/api/papers/assemble", {}, format="json")
    assert resp.status_code == status.HTTP_201_CREATED
    return resp.data


# --- top-level shape ---


@pytest.mark.django_db
def test_schema_version(document):
    """schemaVersion must be exactly 'paper_document.v1' (contract §1)."""
    assert document["schemaVersion"] == "paper_document.v1"


@pytest.mark.django_db
def test_top_level_required_fields(document):
    """All required top-level keys present; no junk keys (contract §1)."""
    required = {"schemaVersion", "request", "template", "format", "paper", "questions"}
    assert required <= set(document.keys())
    # Contract says no empty placeholder objects.
    forbidden_top_level = {"validation", "capabilities", "extensions", "extras"}
    assert not (forbidden_top_level & set(document.keys()))


@pytest.mark.django_db
def test_no_legacy_keys_anywhere(document):
    """No renamed V0 keys appear anywhere in the document (contract rewrite check)."""
    found = _all_keys(document) & _BANNED_KEYS
    assert not found, f"Legacy keys still present: {found}"


# --- request ---


@pytest.mark.django_db
def test_request_shape(document):
    """request has all required fields with correct types (contract §11)."""
    req = document["request"]
    assert req["id"].startswith("req_")
    assert req["language"] == "en"
    assert req["classLevel"] == "10"
    assert req["subject"] == "Science"
    assert req["examType"] in {"full_term", "half_term", "unit_test"}
    filters = req["filters"]
    assert isinstance(filters["chapters"], list)
    assert isinstance(filters["topics"], list)
    assert filters["englishOnly"] is True


# --- template ---


@pytest.mark.django_db
def test_template_shape(document):
    """template carries board / class / marks / duration metadata (contract §11)."""
    tmpl = document["template"]
    for key in (
        "id",
        "name",
        "board",
        "classLevel",
        "subject",
        "examType",
        "totalMarks",
        "durationMinutes",
        "language",
    ):
        assert key in tmpl, f"template missing '{key}'"
    assert tmpl["board"] == "CBSE"
    assert tmpl["classLevel"] == "10"
    assert isinstance(tmpl["totalMarks"], int) and tmpl["totalMarks"] > 0
    assert isinstance(tmpl["durationMinutes"], int) and tmpl["durationMinutes"] > 0


# --- format ---


@pytest.mark.django_db
def test_format_shape(document):
    """format has id + page + layout; geometry and role strings present (§3)."""
    fmt = document["format"]
    assert "id" in fmt
    assert "page" in fmt
    assert "layout" in fmt

    page = fmt["page"]
    for key in ("size", "orientation", "widthPt", "heightPt", "marginPt"):
        assert key in page, f"format.page missing '{key}'"
    margin = page["marginPt"]
    for edge in ("top", "right", "bottom", "left"):
        assert edge in margin

    layout = fmt["layout"]
    for key in (
        "marks",
        "questionNumbers",
        "mcqOptions",
        "instructions",
        "masthead",
        "footer",
    ):
        assert key in layout, f"format.layout missing '{key}'"


# --- paper ---


@pytest.mark.django_db
def test_paper_shape(document):
    """paper has required fields and non-empty sections (contract §4)."""
    paper = document["paper"]
    for key in ("id", "title", "totalMarks", "durationMinutes", "language", "sections"):
        assert key in paper, f"paper missing '{key}'"
    assert paper["id"].startswith("paper_")
    assert isinstance(paper["sections"], list) and len(paper["sections"]) > 0


# --- sections ---


@pytest.mark.django_db
def test_sections_shape(document):
    """Each section has id / title / marks / slots (contract §6)."""
    for section in document["paper"]["sections"]:
        for key in ("id", "title", "marks", "slots"):
            assert key in section, f"section missing '{key}'"
        assert isinstance(section["slots"], list) and len(section["slots"]) > 0
        assert isinstance(section["marks"], int) and section["marks"] >= 0


# --- slots ---


@pytest.mark.django_db
def test_slots_shape(document):
    """Each slot has required fields; number is string, locked is bool (contract §7)."""
    for section in document["paper"]["sections"]:
        for slot in section["slots"]:
            for key in (
                "id",
                "number",
                "marks",
                "type",
                "selectedQuestionId",
                "locked",
                "alternateQuestionIds",
            ):
                assert key in slot, f"slot missing '{key}'"
            assert isinstance(slot["number"], str)
            assert isinstance(slot["locked"], bool)
            assert isinstance(slot["alternateQuestionIds"], list)
            assert isinstance(slot["marks"], int) and slot["marks"] > 0


@pytest.mark.django_db
def test_slot_ids_are_unique(document):
    """Every slot id is unique across the paper (no collision between sections)."""
    all_slot_ids = [
        slot["id"]
        for section in document["paper"]["sections"]
        for slot in section["slots"]
    ]
    assert len(all_slot_ids) == len(set(all_slot_ids))


@pytest.mark.django_db
def test_slot_numbers_are_sequential(document):
    """Slot display numbers run 1, 2, 3, … across all sections (contract §7)."""
    numbers = [
        int(slot["number"])
        for section in document["paper"]["sections"]
        for slot in section["slots"]
    ]
    assert numbers == list(range(1, len(numbers) + 1))


# --- questions ---


@pytest.mark.django_db
def test_questions_shape(document):
    """Each question has all required fields; content is a dict (contract §8–9)."""
    assert len(document["questions"]) > 0
    for q in document["questions"]:
        for key in (
            "id",
            "language",
            "defaultMarks",
            "type",
            "rawText",
            "content",
            "metadata",
            "source",
        ):
            assert key in q, f"question missing '{key}'"
        assert q["id"].startswith("q_")
        assert isinstance(q["content"], dict)
        assert isinstance(q["rawText"], str) and q["rawText"]
        assert isinstance(q["defaultMarks"], int) and q["defaultMarks"] > 0


@pytest.mark.django_db
def test_question_source_shape(document):
    """source has required type and name fields (contract §10)."""
    for q in document["questions"]:
        src = q["source"]
        assert "type" in src, "source missing 'type'"
        assert "name" in src, "source missing 'name'"
        assert src["type"]
        assert src["name"]


@pytest.mark.django_db
def test_selected_question_ids_resolve(document):
    """Every selectedQuestionId resolves to a question in questions[] (contract §7)."""
    question_ids = {q["id"] for q in document["questions"]}
    for section in document["paper"]["sections"]:
        for slot in section["slots"]:
            qid = slot["selectedQuestionId"]
            if qid is not None:
                assert qid in question_ids, (
                    f"slot {slot['id']} selectedQuestionId {qid!r} "
                    f"not in questions[]"
                )


@pytest.mark.django_db
def test_rawtext_does_not_include_mark_annotations(document):
    """rawText must not include visible marks like '[1]' or '(1 mark)' (contract §8)."""
    import re

    mark_pattern = re.compile(r"\[\d+\]|\(\d+ ?marks?\)", re.IGNORECASE)
    for q in document["questions"]:
        assert not mark_pattern.search(
            q["rawText"]
        ), f"question {q['id']} rawText contains mark annotation: {q['rawText']!r}"


@pytest.mark.django_db
def test_content_is_region_keyed_dict(document):
    """question.content is a region-keyed object, not a flat list (contract §9)."""
    for q in document["questions"]:
        content = q["content"]
        assert isinstance(
            content, dict
        ), f"question {q['id']} content is {type(content).__name__}, expected dict"
        # If content has any regions, each must be a list (of ContentItems or objects)
        for region, value in content.items():
            assert isinstance(value, list), (
                f"question {q['id']} content region '{region}' is "
                f"{type(value).__name__}, expected list"
            )


def _image_asset_ids(content) -> set[str]:
    """Collect every `assetId` under an `image`-typed content item, recursively."""
    ids: set[str] = set()
    if isinstance(content, dict):
        if content.get("type") == "image" and "assetId" in content:
            ids.add(content["assetId"])
        for v in content.values():
            ids |= _image_asset_ids(v)
    elif isinstance(content, list):
        for item in content:
            ids |= _image_asset_ids(item)
    return ids


@pytest.mark.django_db
def test_image_assets_resolve_in_storage(document):
    """Every image assetId in question content resolves to a stored file (§9, §135 task 6).

    A stale or mismatched assetId would pass every shape assertion above yet
    404 in the renderer — this is the check that actually proves the asset is
    reachable, not just present-shaped.
    """
    from django.core.files.storage import default_storage

    asset_ids = {
        asset_id
        for q in document["questions"]
        for asset_id in _image_asset_ids(q["content"])
    }
    for asset_id in asset_ids:
        assert default_storage.exists(
            asset_id
        ), f"image assetId {asset_id!r} does not resolve in default_storage"
