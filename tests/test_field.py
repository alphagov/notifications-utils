import pytest

from notifications_utils.field import Field, str2bool


@pytest.mark.parametrize(
    "content",
    [
        "",
        "the quick brown fox",
        """
        the
        quick brown

        fox
    """,
        "the ((quick brown fox",
        "the (()) brown fox",
    ],
)
def test_returns_a_string_without_placeholders(content):
    assert str(Field(content)) == content


@pytest.mark.parametrize(
    "template_content,data,expected",
    [
        ("((colour))", {"colour": "red"}, "red"),
        ("the quick ((colour)) fox", {"colour": "brown"}, "the quick brown fox"),
        (
            "((article)) quick ((colour)) ((animal))",
            {"article": "the", "colour": "brown", "animal": "fox"},
            "the quick brown fox",
        ),
        ("the quick (((colour))) fox", {"colour": "brown"}, "the quick (brown) fox"),
        (
            "the quick ((colour)) fox",
            {"colour": "<script>alert('foo')</script>"},
            "the quick &lt;script&gt;alert('foo')&lt;/script&gt; fox",
        ),
        (
            "before ((placeholder)) after",
            {"placeholder": ""},
            "before  after",
        ),
        (
            "before ((placeholder)) after",
            {"placeholder": "   "},
            "before     after",
        ),
        (
            "before ((placeholder)) after",
            {"placeholder": True},
            "before True after",
        ),
        (
            "before ((placeholder)) after",
            {"placeholder": False},
            "before False after",
        ),
        (
            "before ((placeholder)) after",
            {"placeholder": 0},
            "before 0 after",
        ),
        (
            "before ((placeholder)) after",
            {"placeholder": 0.0},
            "before 0.0 after",
        ),
        (
            "before ((placeholder)) after",
            {"placeholder": 123},
            "before 123 after",
        ),
        (
            "before ((placeholder)) after",
            {"placeholder": 0.1 + 0.2},
            "before 0.30000000000000004 after",
        ),
        (
            "before ((placeholder)) after",
            {"placeholder": {"key": "value"}},
            "before {'key': 'value'} after",
        ),
        ("((warning?))", {"warning?": "This is not a conditional"}, "This is not a conditional"),
        ("((warning?warning))", {"warning?warning": "This is not a conditional"}, "This is not a conditional"),
        ("((warning??This is a conditional warning))", {"warning": True}, "This is a conditional warning"),
        (
            "((warning??This is a conditional warning\nwith line break))",
            {"warning": True},
            "This is a conditional warning\nwith line break",
        ),
        ("((warning??This is a conditional warning))", {"warning": False}, ""),
        (
            "Please report to the ((>location)) office at ((&time)) on ((<day)).",
            {">location": "London", "&time": "09:00", "<day": "Monday"},
            "Please report to the London office at 09:00 on Monday.",
        ),
        (
            "Please report to the ((&gt;location)) office at ((&amp;time)) on ((&lt;day)).",
            {"&gt;location": "Manchester", "&amp;time": "08:00", "&lt;day": "Thursday"},
            "Please report to the Manchester office at 08:00 on Thursday.",
        ),
        (
            "Dear ((\name)), your passport is now ready for collection from ((/collection_point)).",
            {"\name": "Jane Doe", "/collection_point": "Point A"},
            "Dear Jane Doe, your passport is now ready for collection from Point A.",
        ),
        (
            "Dear ((/\name)), your passport is now ready for collection from ((//collection_point)).",
            {"/\name": "John Doe", "//collection_point": "Point B"},
            "Dear John Doe, your passport is now ready for collection from Point B.",
        ),
    ],
)
def test_replacement_of_placeholders(template_content, data, expected):
    assert str(Field(template_content, data)) == expected


@pytest.mark.parametrize(
    "template_content,data,expected",
    [
        ("((code)) is your security code", {"code": "12345"}, "12345 is your security code"),
        (
            "((code)) is your security code",
            {},
            "<span class='placeholder-redacted'>hidden</span> is your security code",
        ),
        (
            "Hey ((name)), click http://example.com/reset-password/?token=((token))",
            {"name": "Example"},
            (
                "Hey Example, click "
                "http://example.com/reset-password/?token="
                "<span class='placeholder-redacted'>hidden</span>"
            ),
        ),
    ],
)
def test_optional_redacting_of_missing_values(template_content, data, expected):
    assert str(Field(template_content, data, redact_missing_personalisation=True)) == expected


@pytest.mark.parametrize(
    "content,expected",
    [
        ("((colour))", "<span class='placeholder'>&#40;&#40;colour&#41;&#41;</span>"),
        ("the quick ((colour)) fox", "the quick <span class='placeholder'>&#40;&#40;colour&#41;&#41;</span> fox"),
        (
            "((article)) quick ((colour)) ((animal))",
            "<span class='placeholder'>&#40;&#40;article&#41;&#41;</span> quick <span class='placeholder'>&#40;&#40;colour&#41;&#41;</span> <span class='placeholder'>&#40;&#40;animal&#41;&#41;</span>",  # noqa
        ),
        (
            """
                ((article)) quick
                ((colour))
                ((animal))
            """,
            """
                <span class='placeholder'>&#40;&#40;article&#41;&#41;</span> quick
                <span class='placeholder'>&#40;&#40;colour&#41;&#41;</span>
                <span class='placeholder'>&#40;&#40;animal&#41;&#41;</span>
            """,
        ),
        ("the quick (((colour))) fox", "the quick (<span class='placeholder'>&#40;&#40;colour&#41;&#41;</span>) fox"),
        ("((warning?))", "<span class='placeholder'>&#40;&#40;warning?&#41;&#41;</span>"),
        (
            "((warning? This is not a conditional))",
            "<span class='placeholder'>&#40;&#40;warning? This is not a conditional&#41;&#41;</span>",
        ),
        (
            "((warning?? This is a warning))",
            "<span class='placeholder-conditional'>&#40;&#40;warning??</span> This is a warning&#41;&#41;",
        ),
        (
            "((warning?? This is a warning\n text after linebreak))",
            "<span class='placeholder-conditional'>&#40;&#40;warning??</span> This is a warning\n text after linebreak&#41;&#41;",  # noqa
        ),
    ],
)
def test_formatting_of_placeholders(content, expected):
    assert str(Field(content)) == expected


@pytest.mark.parametrize(
    "content, values, expected",
    [
        (
            "((name)) ((colour))",
            {"name": "Jo"},
            "Jo <span class='placeholder'>&#40;&#40;colour&#41;&#41;</span>",
        ),
        (
            "((name)) ((colour))",
            {"name": "Jo", "colour": None},
            "Jo <span class='placeholder'>&#40;&#40;colour&#41;&#41;</span>",
        ),
        (
            "((show_thing??thing)) ((colour))",
            {"colour": "red"},
            "<span class='placeholder-conditional'>&#40;&#40;show_thing??</span>thing&#41;&#41; red",
        ),
    ],
)
def test_handling_of_missing_values(content, values, expected):
    assert str(Field(content, values)) == expected


@pytest.mark.parametrize(
    "value",
    [
        "0",
        0,
        2,
        99.99999,
        "off",
        "exclude",
        "no" "any random string",
        "false",
        False,
        [],
        {},
        (),
        ["true"],
        {"True": True},
        (True, "true", 1),
    ],
)
def test_what_will_not_trigger_conditional_placeholder(value):
    assert str2bool(value) is False


@pytest.mark.parametrize("value", [1, "1", "yes", "y", "true", "True", True, "include", "show"])
def test_what_will_trigger_conditional_placeholder(value):
    assert str2bool(value) is True


@pytest.mark.parametrize(
    "values, expected, expected_as_markdown",
    [
        (
            {"placeholder": []},
            "list: ",
            "list: ",
        ),
        (
            {"placeholder": ["", ""]},
            "list: ",
            "list: ",
        ),
        (
            {"placeholder": [" ", " \t ", "\u180E"]},
            "list: ",
            "list: ",
        ),
        (
            {"placeholder": ["one"]},
            "list: one",
            "list: \n\n* one",
        ),
        (
            {"placeholder": ["one", "two"]},
            "list: one and two",
            "list: \n\n* one\n* two",
        ),
        (
            {"placeholder": ["one", "two", "three"]},
            "list: one, two and three",
            "list: \n\n* one\n* two\n* three",
        ),
        (
            {"placeholder": ["one", None, None]},
            "list: one",
            "list: \n\n* one",
        ),
        (
            {"placeholder": ["<script>", 'alert("foo")', "</script>"]},
            'list: &lt;script&gt;, alert("foo") and &lt;/script&gt;',
            'list: \n\n* &lt;script&gt;\n* alert("foo")\n* &lt;/script&gt;',
        ),
        (
            {"placeholder": [1, {"two": 2}, "three", None]},
            "list: 1, {'two': 2} and three",
            "list: \n\n* 1\n* {'two': 2}\n* three",
        ),
        (
            {"placeholder": [[1, 2], [3, 4]]},
            "list: [1, 2] and [3, 4]",
            "list: \n\n* [1, 2]\n* [3, 4]",
        ),
        (
            {"placeholder": [0.1, True, False]},
            "list: 0.1, True and False",
            "list: \n\n* 0.1\n* True\n* False",
        ),
    ],
)
def test_field_renders_lists_as_strings(values, expected, expected_as_markdown):
    assert str(Field("list: ((placeholder))", values, markdown_lists=True)) == expected_as_markdown
    assert str(Field("list: ((placeholder))", values)) == expected
