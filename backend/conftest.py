from collections import Counter

import factory
import pytest
from factory.django import DjangoModelFactory

from accounts.models import School, User
from bank.models import Chapter, Question, QuestionType, Section

# Ambient extraction config that would make tests pick a *live* pipeline. With
# EXTRACTION_PIPELINE=mistral-ocr-* in the shell (a normal dev .env), the drain
# tests would silently call the real Mistral API — a paid, network-dependent
# test run. Tests must always exercise the default injected-fake path unless
# they opt in explicitly.
_LIVE_PIPELINE_ENV_VARS = (
    "EXTRACTION_PIPELINE",
    "MISTRAL_API_KEY",
    "MISTRAL_OCR_API",
)


@pytest.fixture(autouse=True)
def _hermetic_extraction_env(monkeypatch):
    for name in _LIVE_PIPELINE_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


class SchoolFactory(DjangoModelFactory):
    class Meta:
        model = School

    name = factory.Sequence(lambda n: f"School {n}")


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    email = factory.Sequence(lambda n: f"teacher{n}@example.com")
    school = factory.SubFactory(SchoolFactory)

    @factory.post_generation
    def password(self, create, extracted, **kwargs):
        self.set_password(extracted or "pass")
        if create:
            self.save()


class QuestionFactory(DjangoModelFactory):
    class Meta:
        model = Question

    section = Section.A
    qtype = QuestionType.MCQ
    marks = 1
    verified = True  # legacy field, no longer a picker gate (ADR-0002)
    parse_quality = "clean"
    text = factory.Sequence(lambda n: f"Question {n} text?")
    options = factory.LazyFunction(
        lambda: [
            {"label": "A", "text": "Option A"},
            {"label": "B", "text": "Option B"},
            {"label": "C", "text": "Option C"},
            {"label": "D", "text": "Option D"},
        ]
    )
    answer = "A"


@pytest.fixture
def user(db):
    return UserFactory()


@pytest.fixture
def api_client(user):
    from rest_framework.test import APIClient

    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def seeded_bank(db):
    """Seed the minimum questions for the board preset to fill."""
    from papers.template import TemplateBuilder

    spec = TemplateBuilder().build("board")
    needs: Counter = Counter()
    for slot in spec.slots:
        needs[(slot.bank_section, slot.qtype, slot.marks, slot.subject_area)] += 1

    questions = []
    chapter_by_area = {
        area: Chapter.objects.filter(subject_area=area).order_by("order").first()
        for *_, area in needs
        if area
    }
    for (section, qtype, marks, subject_area), count in needs.items():
        for _ in range(count):
            questions.append(
                QuestionFactory(
                    section=section,
                    qtype=qtype,
                    marks=marks,
                    chapter=chapter_by_area.get(subject_area),
                )
            )
    return questions
