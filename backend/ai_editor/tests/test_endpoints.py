"""AI editor endpoint contracts.

These pin the seam the frontend (#28 scaffold, #33/#34 live flows) reads against:
sync intent/chat answer in-request through an injected fake model (no provider,
no network — Rule 13), and the job-creating endpoints persist a pending row,
echo the paper's revision as ``baseRevision``, refuse a second active job on the
same paper, and never confirm another teacher's paper exists.
"""

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from ai_editor import assistant
from ai_editor.models import AIJob, AIJobKind, AIJobStatus
from papers.models import Paper

pytestmark = pytest.mark.django_db


@pytest.fixture
def paper(user):
    # A non-zero revision proves the create endpoints echo the *paper's* revision
    # rather than a hardcoded zero.
    return Paper.objects.create(created_by=user, title="Science — Mock", revision=3)


def _fake_model_returning(content):
    def make_model(_purpose):
        return GenericFakeChatModel(messages=iter([AIMessage(content=content)]))

    return make_model


def test_intent_classifies_typed_text_via_the_model(monkeypatch, api_client, paper):
    monkeypatch.setattr(
        assistant,
        "make_model",
        _fake_model_returning(
            '{"route": "review", "reason": "Asks to check coverage."}'
        ),
    )

    response = api_client.post(
        "/api/ai/intent/",
        {"text": "can you check the paper coverage", "paperId": paper.pk},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["route"] == "review"


def test_intent_coerces_an_unknown_route_to_off_topic(monkeypatch, api_client, paper):
    # A misbehaving model must never widen the routing surface beyond the
    # allowed set — an unknown route is a refusal, not a new capability.
    monkeypatch.setattr(
        assistant,
        "make_model",
        _fake_model_returning('{"route": "delete_everything", "reason": "n/a"}'),
    )

    response = api_client.post(
        "/api/ai/intent/",
        {"text": "rm -rf the paper", "paperId": paper.pk},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["route"] == "off_topic"


def test_chat_answers_read_only_without_exposing_a_provider_key(
    monkeypatch, api_client, paper
):
    monkeypatch.setattr(
        assistant, "make_model", _fake_model_returning("Section B has 6 questions.")
    )

    response = api_client.post(
        "/api/ai/chat/",
        {"text": "how many questions in section B", "paperId": paper.pk},
        format="json",
    )

    assert response.status_code == 200
    assert response.data == {"status": "chat", "message": "Section B has 6 questions."}
    # The contract never leaks server-side provider configuration to the client.
    assert "key" not in str(response.data).lower()


@pytest.mark.parametrize(
    "path,kind",
    [
        ("/api/ai/summarize-paper/", AIJobKind.SUMMARY),
        ("/api/ai/review-paper/", AIJobKind.REVIEW),
        ("/api/ai/editor-edit/", AIJobKind.EDITOR_EDIT),
        ("/api/ai/editor-edit/refine/", AIJobKind.REFINE),
    ],
)
def test_async_endpoint_persists_pending_job_and_returns_202(
    api_client, paper, path, kind
):
    response = api_client.post(path, {"paperId": paper.pk}, format="json")

    assert response.status_code == 202
    assert response.data["status"] == AIJobStatus.PENDING
    assert response.data["kind"] == kind
    # baseRevision is the paper's revision at creation — the drain's cost guard.
    assert response.data["baseRevision"] == paper.revision == 3
    job = AIJob.objects.get(pk=response.data["jobId"])
    assert job.status == AIJobStatus.PENDING and job.base_revision == 3


def test_only_one_active_job_per_paper(api_client, paper):
    first = api_client.post(
        "/api/ai/review-paper/", {"paperId": paper.pk}, format="json"
    )
    assert first.status_code == 202

    second = api_client.post(
        "/api/ai/summarize-paper/", {"paperId": paper.pk}, format="json"
    )

    assert second.status_code == 409
    assert second.data["jobId"] == first.data["jobId"]
    assert AIJob.objects.filter(paper=paper).count() == 1


def test_a_terminal_job_frees_the_paper_for_a_new_one(api_client, paper):
    first = api_client.post(
        "/api/ai/review-paper/", {"paperId": paper.pk}, format="json"
    )
    AIJob.objects.filter(pk=first.data["jobId"]).update(status=AIJobStatus.DONE)

    second = api_client.post(
        "/api/ai/summarize-paper/", {"paperId": paper.pk}, format="json"
    )

    assert second.status_code == 202


def test_another_teachers_paper_is_404_not_403(api_client, db):
    from conftest import UserFactory

    stranger_paper = Paper.objects.create(created_by=UserFactory(), title="Theirs")

    response = api_client.post(
        "/api/ai/review-paper/", {"paperId": stranger_paper.pk}, format="json"
    )

    assert response.status_code == 404
    assert AIJob.objects.count() == 0


def test_job_status_poll_is_owner_scoped(api_client, paper, db):
    from conftest import UserFactory

    own = api_client.post("/api/ai/review-paper/", {"paperId": paper.pk}, format="json")
    stranger_job = AIJob.objects.create(
        paper=Paper.objects.create(created_by=UserFactory(), title="Theirs"),
        kind=AIJobKind.REVIEW,
    )

    poll = api_client.get(f"/api/ai/jobs/{own.data['jobId']}/")
    assert poll.status_code == 200
    assert poll.data["status"] == AIJobStatus.PENDING

    assert api_client.get(f"/api/ai/jobs/{stranger_job.pk}/").status_code == 404
