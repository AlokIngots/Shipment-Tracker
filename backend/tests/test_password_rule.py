"""The password rule: at least 8 characters, a letter and a number (18 Sep 2026).

Was 12 characters of anything. No database needed: the rule is one function,
and every way a password is chosen -- the change screen, the admin
console's Set password, scripts/set_password.py -- goes through it.
"""

import re
from pathlib import Path

import pytest

from app.core import security

RULE_SENTENCE = "Your password needs at least 8 characters, including a letter and a number."


@pytest.mark.parametrize(
    "password",
    ["steel123", "harbour7", "a1b2c3d4", "Größe2026", "kfrn-8mqx-2wtd", "8 letters1"],
)
def test_eight_characters_with_a_letter_and_a_number_are_enough(password):
    assert security.password_problem(password) is None


@pytest.mark.parametrize(
    "password",
    [
        "steel12",       # seven characters
        "harbourside",   # no number
        "12345678",      # no letter
        "--------",      # neither
        "",
    ],
)
def test_anything_less_is_refused_with_the_whole_rule_in_one_sentence(password):
    assert security.password_problem(password) == RULE_SENTENCE


def test_the_old_twelve_character_minimum_is_gone():
    assert security.PASSWORD_MIN_LENGTH == 8
    assert security.password_problem("abcd1234") is None


def test_the_two_existing_refusals_still_hold():
    assert "space" in security.password_problem(" steel123")
    assert "too few different" in security.password_problem("aaaa1111")


def test_every_temporary_password_meets_the_rule():
    """Twelve random picks can come up with no number; they are drawn again."""
    for _ in range(2000):
        assert security.password_problem(security.temporary_password()) is None


def test_the_screens_state_the_same_rule_as_the_server():
    """The frontend keeps its own copy so it can say what is missing while
    typing. Held equal here, so the hint and the refusal cannot drift."""
    rule_js = (
        Path(__file__).resolve().parents[2] / "frontend" / "src" / "lib" / "passwordRule.js"
    ).read_text(encoding="utf-8")
    assert f"PASSWORD_MIN_LENGTH = {security.PASSWORD_MIN_LENGTH}" in rule_js
    stated = re.search(r"PASSWORD_RULE = '([^']+)'", rule_js).group(1)
    assert stated.lower() == security.PASSWORD_RULE.lower()
