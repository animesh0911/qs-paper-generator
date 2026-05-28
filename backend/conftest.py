import pytest
import factory
from factory.django import DjangoModelFactory

from accounts.models import School, User
from bank.models import Question, QuestionType, Section


class SchoolFactory(DjangoModelFactory):
    class Meta:
        model = School

    name = factory.Sequence(lambda n: f"School {n}")


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"teacher{n}@example.com")
    password = factory.PostGenerationMethodCall("set_password", "pass")
    school = factory.SubFactory(SchoolFactory)


class QuestionFactory(DjangoModelFactory):
    class Meta:
        model = Question

    section = Section.A
    qtype = QuestionType.MCQ
    marks = 1
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
    """Seed the minimum questions for SKELETON_PLAN to fill."""
    from papers.assembler import SKELETON_PLAN

    slot_config = {
        Section.A: (QuestionType.MCQ, 1),
        Section.B: (QuestionType.VSA, 2),
        Section.C: (QuestionType.SA, 3),
        Section.D: (QuestionType.LA, 5),
        Section.E: (QuestionType.CASE, 4),
    }
    questions = []
    for section, count in SKELETON_PLAN:
        qtype, marks = slot_config[section]
        for _ in range(count):
            questions.append(
                QuestionFactory(section=section, qtype=qtype, marks=marks)
            )
    return questions
