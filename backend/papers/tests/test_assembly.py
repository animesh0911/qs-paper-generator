"""Integration tests for the paper assembly flow.

These tests verify the interface, not the skeleton implementation. When
BlueprintEngine + SelectionEngine replace the skeleton in Slices 2/3, these
tests still pass or fail loudly.
"""
import pytest
from collections import Counter
from rest_framework import status

from papers.assembler import PaperAssembler
from papers.blueprint import BlueprintEngine
from papers.layout import paper_to_layout


@pytest.mark.django_db
def test_assemble_creates_paper_matching_board_spec(user, seeded_bank):
    """Assembler produces a Paper whose slot counts match the board PaperSpec."""
    spec = BlueprintEngine().build("board")
    paper = PaperAssembler().assemble(user, title="Test Paper")

    assert paper.pk is not None
    assert paper.created_by == user
    assert paper.total_marks == spec.total_marks

    expected_section_counts = Counter(s.section for s in spec.slots)
    actual_section_counts = Counter(item.section for item in paper.items.all())
    assert actual_section_counts == expected_section_counts


@pytest.mark.django_db
def test_assemble_counts_or_group_marks_once(user, seeded_bank):
    """Per-item marks summed across the Paper count each OR-group only once."""
    paper = PaperAssembler().assemble(user)
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
    paper = PaperAssembler().assemble(user)
    spec = BlueprintEngine().build("board")
    assert paper.items.count() == 0
    assert len(paper.report["unfilled"]) == len(spec.slots)


@pytest.mark.django_db
def test_paper_to_layout_round_trips_structure(user, seeded_bank):
    """paper_to_layout produces sections matching the assembled Paper."""
    paper = PaperAssembler().assemble(user)
    layout = paper_to_layout(paper)

    assert layout.title == paper.title
    assert layout.total_marks == paper.total_marks
    assert len(layout.sections) == len({item.section for item in paper.items.all()})
    total_questions = sum(len(s.questions) for s in layout.sections)
    assert total_questions == paper.items.count()


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
    question_ids = {q["questionId"] for q in resp.data["questions"]}
    for section in resp.data["paper"]["sections"]:
        for slot in section["slots"]:
            if slot["selectedQuestionId"] is not None:
                assert slot["selectedQuestionId"] in question_ids


@pytest.mark.django_db
def test_paper_detail_endpoint(api_client, seeded_bank):
    create = api_client.post("/api/papers/assemble", {}, format="json")
    paper_pk = create.data["paper"]["paperId"].removeprefix("paper_")
    detail = api_client.get(f"/api/papers/{paper_pk}/")
    assert detail.status_code == status.HTTP_200_OK
    assert str(detail.data["id"]) == paper_pk


@pytest.mark.django_db
def test_paper_pdf_endpoint_returns_pdf_bytes(api_client, seeded_bank):
    create = api_client.post("/api/papers/assemble", {}, format="json")
    paper_pk = create.data["paper"]["paperId"].removeprefix("paper_")
    pdf = api_client.get(f"/api/papers/{paper_pk}/pdf/")
    assert pdf.status_code == status.HTTP_200_OK
    assert pdf["Content-Type"] == "application/pdf"
    assert pdf.content[:4] == b"%PDF"
