import pytest
from unittest.mock import Mock

from bank.policy import answer_visible


def _user(is_staff=False, is_authenticated=True):
    u = Mock()
    u.is_staff = is_staff
    u.is_authenticated = is_authenticated
    return u


def test_staff_user_can_see_answers():
    assert answer_visible(_user(is_staff=True)) is True


def test_regular_user_cannot_see_answers():
    assert answer_visible(_user(is_staff=False)) is False


def test_unauthenticated_user_cannot_see_answers():
    assert answer_visible(_user(is_authenticated=False)) is False


def test_none_user_cannot_see_answers():
    assert answer_visible(None) is False
