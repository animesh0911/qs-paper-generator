"""Integration tests for the paper assembly flow.

These tests verify the interface, not the skeleton implementation. When
TemplateBuilder + QuestionPicker replace the skeleton in Slices 2/3, these
tests still pass or fail loudly.
"""

from collections import Counter

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
    question_ids = {q["questionId"] for q in resp.data["questions"]}
    for section in resp.data["paper"]["sections"]:
        for slot in section["slots"]:
            if slot["selectedQuestionId"] is not None:
                assert slot["selectedQuestionId"] in question_ids


@pytest.mark.django_db
def test_paper_detail_returns_stored_document(api_client, seeded_bank):
    create = api_client.post("/api/papers/assemble", {}, format="json")
    paper_pk = create.data["paper"]["paperId"].removeprefix("paper_")
    detail = api_client.get(f"/api/papers/{paper_pk}/")
    assert detail.status_code == status.HTTP_200_OK
    assert detail.data["schemaVersion"] == "paper_document.v1"


@pytest.mark.django_db
def test_patch_saves_edited_document(api_client, seeded_bank):
    create = api_client.post("/api/papers/assemble", {}, format="json")
    paper_pk = create.data["paper"]["paperId"].removeprefix("paper_")
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
    paper_pk = create.data["paper"]["paperId"].removeprefix("paper_")
    bad_doc = {"schemaVersion": "wrong.v1"}
    resp = api_client.patch(
        f"/api/papers/{paper_pk}/", {"document": bad_doc}, format="json"
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_approve_locks_paper(api_client, seeded_bank):
    create = api_client.post("/api/papers/assemble", {}, format="json")
    paper_pk = create.data["paper"]["paperId"].removeprefix("paper_")
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
def test_approve_freezes_submitted_final_document(api_client, seeded_bank):
    """Approval freezes the teacher's final PaperDocumentV1, not the stale draft."""
    create = api_client.post("/api/papers/assemble", {}, format="json")
    paper_pk = create.data["paper"]["paperId"].removeprefix("paper_")
    final_doc = dict(create.data)
    final_doc["paper"] = dict(final_doc["paper"])
    final_doc["paper"]["title"] = "Final Approved Title"

    approve = api_client.post(
        f"/api/papers/{paper_pk}/approve/",
        {"document": final_doc},
        format="json",
    )

    assert approve.status_code == status.HTTP_200_OK
    detail = api_client.get(f"/api/papers/{paper_pk}/")
    assert detail.data["paper"]["title"] == "Final Approved Title"


@pytest.mark.django_db
def test_approve_rejects_structural_errors(api_client, seeded_bank):
    """Approval must block documents with missing selected Question references."""
    create = api_client.post("/api/papers/assemble", {}, format="json")
    paper_pk = create.data["paper"]["paperId"].removeprefix("paper_")
    invalid_doc = dict(create.data)
    invalid_doc["paper"] = dict(invalid_doc["paper"])
    invalid_doc["paper"]["sections"] = [
        dict(section) for section in create.data["paper"]["sections"]
    ]
    invalid_doc["paper"]["sections"][0]["slots"] = [
        dict(slot) for slot in invalid_doc["paper"]["sections"][0]["slots"]
    ]
    invalid_doc["paper"]["sections"][0]["slots"][0]["selectedQuestionId"] = "q_missing"

    approve = api_client.post(
        f"/api/papers/{paper_pk}/approve/",
        {"document": invalid_doc},
        format="json",
    )

    assert approve.status_code == status.HTTP_400_BAD_REQUEST
    detail = api_client.get(f"/api/papers/{paper_pk}/")
    assert (
        detail.data["paper"]["sections"][0]["slots"][0]["selectedQuestionId"]
        != "q_missing"
    )


@pytest.mark.django_db
def test_approve_flips_verified_on_referenced_questions(api_client, seeded_bank):
    """ADR-0002: approving a paper marks every referenced question verified=True.

    The verified flag changed semantics — it no longer gates the picker (Q.parse_quality
    does). It now records "a human has seen this question in an approved paper context."
    This test pins that behavior so future regressions surface immediately.
    """
    from bank.models import Question

    Question.objects.update(verified=False)  # reset seeded fixture
    create = api_client.post("/api/papers/assemble", {}, format="json")
    paper_pk = create.data["paper"]["paperId"].removeprefix("paper_")
    selected_ids = {
        int(slot["selectedQuestionId"].removeprefix("q_"))
        for section in create.data["paper"]["sections"]
        for slot in section["slots"]
        if slot["selectedQuestionId"] is not None
    }
    assert selected_ids, "assembler must have placed at least one question"

    api_client.post(f"/api/papers/{paper_pk}/approve/")
    verified_ids = set(
        Question.objects.filter(pk__in=selected_ids, verified=True).values_list(
            "pk", flat=True
        )
    )
    assert verified_ids == selected_ids


@pytest.mark.django_db
def test_picker_excludes_broken_parse_quality(api_client, seeded_bank):
    """Picker must skip broken rows even if section/qtype/marks match."""
    from bank.models import Question

    Question.objects.update(parse_quality="broken")
    resp = api_client.post("/api/papers/assemble", {}, format="json")
    # Best-effort: best assembly with no eligible questions = all slots unfilled.
    selected = [
        slot["selectedQuestionId"]
        for section in resp.data["paper"]["sections"]
        for slot in section["slots"]
    ]
    assert all(s is None for s in selected), "broken rows must not be picked"


@pytest.mark.django_db
def test_picker_includes_partial_parse_quality(api_client, seeded_bank):
    """parse_quality='partial' rows must be pickable — only 'broken' is excluded."""
    from bank.models import Question

    Question.objects.update(parse_quality="partial")
    resp = api_client.post("/api/papers/assemble", {}, format="json")
    selected = [
        slot["selectedQuestionId"]
        for section in resp.data["paper"]["sections"]
        for slot in section["slots"]
        if slot["selectedQuestionId"] is not None
    ]
    assert selected, "partial rows must be eligible for the picker"


@pytest.mark.django_db
def test_assemble_response_includes_format_object(api_client, seeded_bank):
    """Assemble response must include top-level format satisfying V1 contract."""
    resp = api_client.post("/api/papers/assemble", {}, format="json")
    assert resp.status_code == status.HTTP_201_CREATED
    fmt = resp.data.get("format")
    assert fmt is not None, "format object missing from response"
    assert fmt["formatId"] == "cbse_science_class_10_v1"
    assert fmt["page"]["size"] == "A4"
    assert fmt["page"]["orientation"] == "portrait"
    assert "paperChrome" in fmt
    assert "numbering" in fmt
    assert fmt["sections"]["allowCrossSectionMove"] is False
    assert fmt["questionRegions"]["allowRegionReorder"] is False
    assert fmt["questionRegions"]["allowRegionDelete"] is False
    assert fmt["mcqOptions"]["layout"] == "vertical"


@pytest.mark.django_db
def test_every_slot_has_alternate_question_ids(api_client, seeded_bank):
    """Every slot must include alternateQuestionIds ([] when no alternates exist)."""
    resp = api_client.post("/api/papers/assemble", {}, format="json")
    assert resp.status_code == status.HTTP_201_CREATED
    for section in resp.data["paper"]["sections"]:
        for slot in section["slots"]:
            assert (
                "alternateQuestionIds" in slot
            ), f"slot {slot.get('slotId')} missing alternateQuestionIds"
            assert isinstance(slot["alternateQuestionIds"], list)


@pytest.mark.django_db
def test_paper_pdf_endpoint_returns_pdf_bytes(api_client, seeded_bank):
    create = api_client.post("/api/papers/assemble", {}, format="json")
    paper_pk = create.data["paper"]["paperId"].removeprefix("paper_")
    pdf = api_client.get(f"/api/papers/{paper_pk}/pdf/")
    assert pdf.status_code == status.HTTP_200_OK
    assert pdf["Content-Type"] == "application/pdf"
    assert pdf.content[:4] == b"%PDF"
