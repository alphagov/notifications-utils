import re

import pytest

from notifications_utils.field import ConditionalPlaceholder, Placeholder


@pytest.mark.parametrize(
    "body, expected",
    [
        ("((with-brackets))", "with-brackets"),
        ("without-brackets", "without-brackets"),
    ],
)
def test_placeholder_returns_name(body, expected):
    assert Placeholder(body).name == expected


@pytest.mark.parametrize(
    "body, is_conditional",
    [
        ("not a conditional", False),
        ("not? a conditional", False),
        ("a?? conditional", True),
    ],
)
def test_placeholder_identifies_conditional(body, is_conditional):
    assert isinstance(Placeholder(body), ConditionalPlaceholder) == is_conditional


@pytest.mark.parametrize(
    "body, conditional_text",
    [
        ("a??b", "b"),
        ("a?? b ", " b "),
        ("a??b??c", "b??c"),
    ],
)
def test_placeholder_gets_conditional_text(body, conditional_text):
    assert Placeholder(body).conditional_text == conditional_text


@pytest.mark.parametrize(
    "body, value, result",
    [
        ("a??b", "Yes", "b"),
        ("a??b", "No", ""),
    ],
)
def test_placeholder_gets_conditional_body(body, value, result):
    assert Placeholder(body).replace_with(value) == result


def test_placeholder_can_be_constructed_from_regex_match():
    match = re.search(r"\(\(.*\)\)", "foo ((bar)) baz")
    assert Placeholder.from_match(match).name == "bar"
