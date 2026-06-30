"""Tests for the browsable Question Bank endpoint (``GET /api/bank/questions/``).

Covers tenancy (global bank + own school, never another school's), the
chapter/section/qtype/source filters, text search, limit/offset pagination,
the ``IsTeacher`` gate, and that ``answer`` is never serialized.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from accounts.models import School, User
from bank.models import Chapter, Question, QuestionType, Section, SourceType

pytestmark = pytest.mark.django_db


def _question(**kwargs):
    defaults = dict(
        section=Section.A,
        qtype=QuestionType.MCQ,
        marks=1,
        text="Default question text?",
        answer="A",
        parse_quality="clean",
    )
    defaults.update(kwargs)
    return Question.objects.create(**defaults)


def test_lists_global_and_own_school_questions(api_client, user):
    """A teacher sees the global bank plus their own school's questions."""
    _question(text="Global one")
    _question(text="Mine", school=user.school)

    resp = api_client.get("/api/bank/questions/")

    assert resp.status_code == 200
    texts = {q["text"] for q in resp.data["results"]}
    assert texts == {"Global one", "Mine"}
    assert resp.data["count"] == 2


def test_hides_other_schools_questions(api_client, user):
    """Another school's questions never appear in the teacher's view."""
    other = School.objects.create(name="Other School")
    _question(text="Visible", school=user.school)
    _question(text="Hidden", school=other)

    resp = api_client.get("/api/bank/questions/")

    texts = {q["text"] for q in resp.data["results"]}
    assert texts == {"Visible"}


def test_never_exposes_answer(api_client):
    """The serialized question must not leak the answer key."""
    _question(text="Q", answer="secret")

    resp = api_client.get("/api/bank/questions/")

    assert "answer" not in resp.data["results"][0]


def test_excludes_broken_questions(api_client):
    """Broken rows (empty/fragment stems) are unusable by the picker, so the
    bank view — which shows "what's available" — must hide them too."""
    _question(text="Usable", parse_quality="clean")
    _question(text="(b)", parse_quality="broken")

    resp = api_client.get("/api/bank/questions/")

    texts = {q["text"] for q in resp.data["results"]}
    assert texts == {"Usable"}


def test_filters_by_section_qtype_and_source(api_client):
    _question(text="A1", section=Section.A, qtype=QuestionType.MCQ)
    _question(
        text="C3",
        section=Section.C,
        qtype=QuestionType.SA,
        marks=3,
        source_type=SourceType.SAMPLE_PAPER,
    )

    by_section = api_client.get("/api/bank/questions/", {"section": Section.C})
    assert {q["text"] for q in by_section.data["results"]} == {"C3"}

    by_source = api_client.get(
        "/api/bank/questions/", {"source_type": SourceType.SAMPLE_PAPER}
    )
    assert {q["text"] for q in by_source.data["results"]} == {"C3"}


def test_filters_by_chapter_slug(api_client):
    chapter = Chapter.objects.first()
    _question(text="In chapter", chapter=chapter)
    _question(text="No chapter")

    resp = api_client.get("/api/bank/questions/", {"chapter": chapter.slug})

    assert {q["text"] for q in resp.data["results"]} == {"In chapter"}


def test_search_matches_question_text(api_client):
    _question(text="What is photosynthesis?")
    _question(text="Define velocity.")

    resp = api_client.get("/api/bank/questions/", {"search": "photo"})

    assert {q["text"] for q in resp.data["results"]} == {"What is photosynthesis?"}


def test_pagination_limits_and_reports_count(api_client):
    for i in range(5):
        _question(text=f"Q{i}")

    resp = api_client.get("/api/bank/questions/", {"limit": 2, "offset": 0})

    assert resp.data["count"] == 5
    assert len(resp.data["results"]) == 2
    assert resp.data["limit"] == 2
    assert resp.data["offset"] == 0


def test_requires_teacher_account(db):
    """A user without a school is refused (the IsTeacher gate)."""
    schoolless = User.objects.create_user(email="noschool@example.com", password="pass")
    client = APIClient()
    client.force_authenticate(user=schoolless)

    resp = client.get("/api/bank/questions/")

    assert resp.status_code == 403


def test_requires_authentication():
    assert APIClient().get("/api/bank/questions/").status_code in (401, 403)
