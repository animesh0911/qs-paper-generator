"""Integration tests for the paper assembly flow.

These tests verify the interface, not the skeleton implementation. When
TemplateBuilder + QuestionPicker replace the skeleton in Slices 2/3, these
tests still pass or fail loudly.
"""

from collections import Counter

import fitz
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
def test_approve_marks_referenced_questions_verified(api_client, seeded_bank):
    """Approving a paper flips ``verified=True`` on its selected questions (ADR-0002).

    Why this matters: ``verified`` is the only signal that a human vetted a
    question in a real paper. If approve doesn't write it, the flag CONTEXT.md and
    ADR-0002 promise stays permanently false and analytics built on it are blind."""
    from bank.models import Question

    create = api_client.post("/api/papers/assemble", {}, format="json")
    document = create.data
    paper_pk = document["paper"]["id"].removeprefix("paper_")
    selected_pks = {
        int(slot["selectedQuestionId"].removeprefix("q_"))
        for section in document["paper"]["sections"]
        for slot in section["slots"]
        if slot.get("selectedQuestionId")
    }
    assert selected_pks  # the seeded bank fills at least one slot
    # Arrange the unverified pre-state explicitly (seed rows ship verified=True).
    Question.objects.filter(pk__in=selected_pks).update(verified=False)

    api_client.post(f"/api/papers/{paper_pk}/approve/")

    # Every selected question is flipped; none left unverified.
    assert not Question.objects.filter(pk__in=selected_pks, verified=False).exists()


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

    with fitz.open(stream=pdf.content, filetype="pdf") as rendered:
        text = "\n".join(page.get_text() for page in rendered)
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


def _pdf_text(pdf_bytes: bytes) -> str:
    with fitz.open(stream=pdf_bytes, filetype="pdf") as rendered:
        return "\n".join(page.get_text() for page in rendered)


def _first_selected_qid(document: dict) -> str:
    for section in document["paper"]["sections"]:
        for slot in section["slots"]:
            if slot.get("selectedQuestionId"):
                return slot["selectedQuestionId"]
    raise AssertionError("seeded bank must fill at least one slot")


@pytest.mark.django_db
def test_answer_key_pdf_endpoint_renders_stored_answers(api_client, seeded_bank):
    """The marking-scheme endpoint joins the canonical paper with bank answers.

    The answer text lives only on the Question row (never the document), so this
    proves the gated join reaches the PDF — not that a constant was printed.
    """
    from bank.models import Question

    create = api_client.post("/api/papers/assemble", {}, format="json")
    document = create.data
    paper_pk = document["paper"]["id"].removeprefix("paper_")
    qid = _first_selected_qid(document)
    selected_pk = int(qid.removeprefix("q_"))
    Question.objects.filter(pk=selected_pk).update(answer="UNIQUE_MARKING_ANSWER_42")

    resp = api_client.get(f"/api/papers/{paper_pk}/answer-key/pdf/")

    assert resp.status_code == status.HTTP_200_OK
    assert resp["Content-Type"] == "application/pdf"
    assert resp.content[:4] == b"%PDF"
    assert "UNIQUE_MARKING_ANSWER_42" in _pdf_text(resp.content)


@pytest.mark.django_db
def test_answer_never_leaks_through_assemble_or_detail(api_client, seeded_bank):
    """Answers must stay behind the answer-key endpoint — never in paper JSON.

    Guards the gate: if a future serializer change started echoing ``answer``
    into the document's questions, the marking key would leak to every client
    that can fetch the paper.
    """
    create = api_client.post("/api/papers/assemble", {}, format="json")
    paper_pk = create.data["paper"]["id"].removeprefix("paper_")
    detail = api_client.get(f"/api/papers/{paper_pk}/")

    for payload in (create.data, detail.data):
        for question in payload["questions"]:
            assert "answer" not in question


@pytest.mark.django_db
def test_answer_key_pdf_endpoint_is_owner_scoped(api_client, seeded_bank):
    """Another teacher cannot pull a paper's answers — owner-scoped, 404 not 403.

    A 404 (not 403) keeps the paper's existence private; either way answers
    never cross to a non-owner request.
    """
    from rest_framework.test import APIClient

    from accounts.models import User

    create = api_client.post("/api/papers/assemble", {}, format="json")
    paper_pk = create.data["paper"]["id"].removeprefix("paper_")

    intruder = User.objects.create_user(email="intruder@example.com", password="x")
    intruder_client = APIClient()
    intruder_client.force_authenticate(intruder)

    resp = intruder_client.get(f"/api/papers/{paper_pk}/answer-key/pdf/")

    assert resp.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_branding_flows_from_school_settings_to_document_and_pdf(
    api_client, user, seeded_bank, settings
):
    """A school's branding reaches both the contract and the rendered PDF.

    Branding is configured on the School row (no code change). This asserts the
    end-to-end path: settings -> document.paper.branding -> PDF header. Forces
    the ReportLab path so the assertion does not depend on a running browser.
    """
    settings.PAPER_PRINT_BASE_URL = ""
    user.school.settings = {
        "branding": {
            "schoolName": "Greenwood High School",
            "examHeader": "Half-Yearly Examination 2026",
        }
    }
    user.school.save()

    create = api_client.post("/api/papers/assemble", {}, format="json")
    document = create.data
    paper_pk = document["paper"]["id"].removeprefix("paper_")

    assert document["paper"]["branding"] == {
        "schoolName": "Greenwood High School",
        "examHeader": "Half-Yearly Examination 2026",
    }

    pdf = api_client.get(f"/api/papers/{paper_pk}/pdf/")
    text = _pdf_text(pdf.content)
    assert "Greenwood High School" in text
    assert "Half-Yearly Examination 2026" in text


@pytest.mark.django_db
def test_approve_records_question_usage_for_the_teacher(api_client, user, seeded_bank):
    """Approving a paper records QuestionUsage for its selected questions (Slice 10).

    Why this matters: usage is the freshness signal. If approve does not write
    it, the picker can never deprioritise a repeat and successive papers stay
    stale.
    """
    from papers.models import QuestionUsage

    create = api_client.post("/api/papers/assemble", {}, format="json")
    document = create.data
    paper_pk = int(document["paper"]["id"].removeprefix("paper_"))
    selected_pks = {
        int(slot["selectedQuestionId"].removeprefix("q_"))
        for section in document["paper"]["sections"]
        for slot in section["slots"]
        if slot.get("selectedQuestionId")
    }
    assert selected_pks

    api_client.post(f"/api/papers/{paper_pk}/approve/")

    usages = QuestionUsage.objects.filter(paper_id=paper_pk)
    assert set(usages.values_list("question_id", flat=True)) == selected_pks
    assert all(u.used_by_id == user.id for u in usages)


@pytest.mark.django_db
def test_reapproving_a_paper_does_not_double_count_usage(user, seeded_bank):
    """Re-running approve adds no duplicate usage — approval stays idempotent.

    Why this matters: the per-question unique constraint plus ignore_conflicts
    must hold, or a re-approve would inflate a question's usage count and skew
    freshness against it.
    """
    from papers.models import QuestionUsage

    paper = PaperBuilder().assemble(user).paper
    paper.approve()
    first = QuestionUsage.objects.filter(paper=paper).count()
    assert first > 0

    paper.approve()
    assert QuestionUsage.objects.filter(paper=paper).count() == first
