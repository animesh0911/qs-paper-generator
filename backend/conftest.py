import pytest
import factory
from collections import Counter
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
    verified = True
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
        needs[(slot.section, slot.qtype, slot.marks)] += 1

    questions = []
    for (section, qtype, marks), count in needs.items():
        for _ in range(count):
            questions.append(
                QuestionFactory(section=section, qtype=qtype, marks=marks)
            )
    return questions
