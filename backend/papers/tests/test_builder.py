"""Integration tests for the paper assembly flow.

These tests verify the interface, not the skeleton implementation. When
TemplateBuilder + QuestionPicker replace the skeleton in Slices 2/3, these
tests still pass or fail loudly.
"""

from collections import Counter
from io import BytesIO

import pdfplumber
import pytest
from rest_framework import status

from papers.builder import PaperBuilder
from papers.template import TemplateBuilder


@pytest.mark.django_db
def test_assemble_creates_paper_matching_board_spec(user, seeded_bank):
    """Assembler produces a Paper whose slot counts match the board PaperTemplate."""
    spec = TemplateBuilder().build("board")
    paper = PaperBuilder().assemble(user, title="Test Paper").paper

    assert paper.pk is not None
    assert paper.created_by == user
    assert paper.total_marks == spec.total_marks

    expected_section_counts = Counter(s.section for s in spec.slots)
    actual_section_counts = Counter(item.section for item in paper.items.all())
    assert actual_section_counts == expected_section_counts


@pytest.mark.django_db
def test_assemble_counts_or_group_marks_once(user, seeded_bank):
    """Per-item marks summed across the Paper count each OR-group only once."""
    paper = PaperBuilder().assemble(user).paper
    seen_groups: set[int] = set()
    total = 0
    for item in paper.items.select_related("question"):
        if item.or_group is None:
            total += item.question.marks
        elif item.or_group not in seen_groups:
            seen_groups.add(item.or_group)
            total += item.question.marks
    assert total == paper.total_marks
    assert seen_groups, "board preset must produce at least one OR-group"


@pytest.mark.django_db
def test_assemble_best_effort_when_bank_empty(user, db):
    """Empty bank produces a paper with no items and every slot reported as unfilled.

    Best-effort policy (Slice 3): the engine never raises on insufficient pool;
    teachers must be able to see which slots failed so they can fix inputs.
    """
    paper = PaperBuilder().assemble(user).paper
    spec = TemplateBuilder().build("board")
    assert paper.items.count() == 0
    assert len(paper.report["unfilled"]) == len(spec.slots)


@pytest.mark.django_db
def test_assemble_endpoint_returns_document(api_client, seeded_bank):
    resp = api_client.post("/api/papers/assemble", {}, format="json")
    assert resp.status_code == status.HTTP_201_CREATED
    assert resp.data["schemaVersion"] == "paper_document.v1"
    assert resp.data["paper"]["totalMarks"] > 0
    assert len(resp.data["questions"]) > 0
    assert len(resp.data["paper"]["sections"]) > 0


@pytest.mark.django_db
def test_document_slots_reference_questions_array(api_client, seeded_bank):
    resp = api_client.post("/api/papers/assemble", {}, format="json")
    question_ids = {q["id"] for q in resp.data["questions"]}
    for section in resp.data["paper"]["sections"]:
        for slot in section["slots"]:
            if slot["selectedQuestionId"] is not None:
                assert slot["selectedQuestionId"] in question_ids


@pytest.mark.django_db
def test_paper_detail_returns_stored_document(api_client, seeded_bank):
    create = api_client.post("/api/papers/assemble", {}, format="json")
    paper_pk = create.data["paper"]["id"].removeprefix("paper_")
    detail = api_client.get(f"/api/papers/{paper_pk}/")
    assert detail.status_code == status.HTTP_200_OK
    assert detail.data["schemaVersion"] == "paper_document.v1"


@pytest.mark.django_db
def test_patch_saves_edited_document(api_client, seeded_bank):
    create = api_client.post("/api/papers/assemble", {}, format="json")
    paper_pk = create.data["paper"]["id"].removeprefix("paper_")
    edited_doc = dict(create.data)
    edited_doc["paper"] = dict(edited_doc["paper"])
    edited_doc["paper"]["title"] = "Edited Title"
    resp = api_client.patch(
        f"/api/papers/{paper_pk}/",
        {"document": edited_doc},
        format="json",
    )
    assert resp.status_code == status.HTTP_200_OK
    detail = api_client.get(f"/api/papers/{paper_pk}/")
    assert detail.data["paper"]["title"] == "Edited Title"


@pytest.mark.django_db
def test_patch_rejected_wrong_schema(api_client, seeded_bank):
    create = api_client.post("/api/papers/assemble", {}, format="json")
    paper_pk = create.data["paper"]["id"].removeprefix("paper_")
    bad_doc = {"schemaVersion": "wrong.v1"}
    resp = api_client.patch(
        f"/api/papers/{paper_pk}/", {"document": bad_doc}, format="json"
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_approve_locks_paper(api_client, seeded_bank):
    create = api_client.post("/api/papers/assemble", {}, format="json")
    paper_pk = create.data["paper"]["id"].removeprefix("paper_")
    approve = api_client.post(f"/api/papers/{paper_pk}/approve/")
    assert approve.status_code == status.HTTP_200_OK
    assert approve.data["status"] == "approved"
    # Further PATCH rejected
    resp = api_client.patch(
        f"/api/papers/{paper_pk}/",
        {"document": create.data},
        format="json",
    )
    assert resp.status_code == status.HTTP_409_CONFLICT


@pytest.mark.django_db
def test_paper_pdf_endpoint_returns_pdf_bytes(api_client, seeded_bank):
    create = api_client.post("/api/papers/assemble", {}, format="json")
    paper_pk = create.data["paper"]["id"].removeprefix("paper_")
    pdf = api_client.get(f"/api/papers/{paper_pk}/pdf/")
    assert pdf.status_code == status.HTTP_200_OK
    assert pdf["Content-Type"] == "application/pdf"
    assert pdf.content[:4] == b"%PDF"


@pytest.mark.django_db
def test_paper_pdf_endpoint_uses_saved_document_edits(
    api_client, seeded_bank, settings
):
    """PDF download must render the edited PaperDocumentV1, not bank text."""
    settings.PAPER_PRINT_BASE_URL = ""
    create = api_client.post("/api/papers/assemble", {}, format="json")
    paper_pk = create.data["paper"]["id"].removeprefix("paper_")
    edited_doc = dict(create.data)
    edited_doc["questions"] = [dict(q) for q in edited_doc["questions"]]
    # Edit the canonical render path: the renderer prefers content.stem over
    # rawText, so an edit must land in the structured region to reach the PDF.
    edited_question = edited_doc["questions"][0]
    edited_question["content"] = {
        **edited_question["content"],
        "stem": [{"type": "paragraph", "text": "Edited slot text for the saved draft"}],
    }
    api_client.patch(
        f"/api/papers/{paper_pk}/",
        {"document": edited_doc},
        format="json",
    )

    pdf = api_client.get(f"/api/papers/{paper_pk}/pdf/")

    with pdfplumber.open(BytesIO(pdf.content)) as rendered:
        text = "\n".join(page.extract_text() or "" for page in rendered.pages)
    assert "Edited slot text for the saved draft" in text


@pytest.mark.django_db
def test_paper_pdf_endpoint_targets_print_route_with_auth_token(
    api_client, monkeypatch, seeded_bank, settings
):
    """Browser PDF rendering goes through the React print route for parity."""
    settings.PAPER_PRINT_BASE_URL = "http://frontend:5173"
    create = api_client.post("/api/papers/assemble", {}, format="json")
    paper_pk = create.data["paper"]["id"].removeprefix("paper_")
    calls = []

    def fake_render(document, print_url=None):
        calls.append((document, print_url))
        return b"%PDF from-browser"

    monkeypatch.setattr("papers.views.render_paper_pdf", fake_render)

    pdf = api_client.get(f"/api/papers/{paper_pk}/pdf/")

    assert pdf.status_code == status.HTTP_200_OK
    assert calls[0][0]["schemaVersion"] == "paper_document.v1"
    assert calls[0][1].startswith(
        f"http://frontend:5173/editor/{paper_pk}/print?token="
    )
