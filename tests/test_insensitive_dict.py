from functools import partial

import pytest
from ordered_set import OrderedSet

from notifications_utils.insensitive_dict import InsensitiveDict, InsensitiveSet
from notifications_utils.recipients import Cell, Row


def test_columns_as_dict_with_keys():
    assert InsensitiveDict({"Date of Birth": "01/01/2001", "TOWN": "London"}).as_dict_with_keys(
        {"date_of_birth", "town"}
    ) == {"date_of_birth": "01/01/2001", "town": "London"}


def test_columns_as_dict():
    assert dict(InsensitiveDict({"date of birth": "01/01/2001", "TOWN": "London"})) == {
        "dateofbirth": "01/01/2001",
        "town": "London",
    }


def test_missing_data():
    partial_row = partial(
        Row,
        row_dict={},
        index=1,
        error_fn=None,
        recipient_column_headers=[],
        placeholders=[],
        template=None,
        allow_international_letters=False,
    )
    with pytest.raises(KeyError):
        InsensitiveDict({})["foo"]
    assert InsensitiveDict({}).get("foo") is None
    assert InsensitiveDict({}).get("foo", "bar") == "bar"
    assert partial_row()["foo"] == Cell()
    assert partial_row().get("foo") == Cell()
    assert partial_row().get("foo", "bar") == "bar"


@pytest.mark.parametrize(
    "in_dictionary",
    [
        {"foo": "bar"},
        {"F_O O": "bar"},
    ],
)
@pytest.mark.parametrize(
    "key, should_be_present",
    [
        ("foo", True),
        ("f_o_o", True),
        ("F O O", True),
        ("bar", False),
    ],
)
def test_lookup(key, should_be_present, in_dictionary):
    assert (key in InsensitiveDict(in_dictionary)) == should_be_present


@pytest.mark.parametrize(
    "key_in",
    [
        "foo",
        "F_O O",
    ],
)
@pytest.mark.parametrize(
    "lookup_key",
    [
        "foo",
        "f_o_o",
        "F O O",
    ],
)
def test_set_item(key_in, lookup_key):
    columns = InsensitiveDict({})
    columns[key_in] = "bar"
    assert columns[lookup_key] == "bar"


def test_maintains_insertion_order():
    d = InsensitiveDict(
        {
            "B": None,
            "A": None,
            "C": None,
        }
    )
    assert d.keys() == ["b", "a", "c"]
    d["BB"] = None
    assert d.keys() == ["b", "a", "c", "bb"]


def test_insensitive_set():
    assert InsensitiveSet(
        [
            "foo",
            "F o o ",
            "F_O_O",
            "B_A_R",
            "B a r",
            "bar",
        ]
    ) == OrderedSet(
        [
            "foo",
            "B_A_R",
        ]
    )


@pytest.mark.parametrize(
    "extra_args, expected_dict",
    (
        ({}, {"foo": 3}),
        ({"overwrite_duplicates": True}, {"foo": 3}),
        ({"overwrite_duplicates": False}, {"foo": 1}),
    ),
)
def test_overwrite_duplicates(extra_args, expected_dict):
    assert InsensitiveDict({"foo": 1, "FOO": 2, "f_o_o": 3}, **extra_args) == expected_dict
