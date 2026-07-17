from functools import partial

import pytest

from notifications_utils.insensitive_dict import InsensitiveDict, InsensitiveSet
from notifications_utils.recipients import Cell, Row
from notifications_utils.template import SMSPreviewTemplate


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
    template = SMSPreviewTemplate({"content": "foo", "template_type": "sms"})
    partial_row = partial(
        Row,
        row_dict={},
        index=1,
        error_fn=None,
        recipient_column_headers=[],
        placeholders=[],
        template=template,
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
    assert tuple(
        InsensitiveSet(
            [
                "foo",
                "F o o ",
                "F_O_O",
                "B_A_R",
                "B a r",
                "bar",
            ]
        )
    ) == (
        # Items match their first-seen format
        "foo",
        "B_A_R",
    )


def test_insensitive_set_contains():
    foobar = InsensitiveSet(("foo", "bar"))

    for key in (
        "foo",
        "F o o ",
        "F_O_O",
        "B_A_R",
        "B a r",
        "bar",
    ):
        assert key in foobar

    for key in (
        "baz",
        "barz",
        "z foo",
    ):
        assert key not in foobar


def test_key_stored_as_normalised_format():
    assert tuple(InsensitiveDict({"foo": 1, "FOO": 2, "f_o_o": 3}).items()) == (("foo", 3),)


def test_insensitive_set_index():
    foobarbaz = InsensitiveSet(("foo", "bar", "FOO", "BAR", "B A Z"))

    assert foobarbaz.index("foo") == foobarbaz.index("FOO") == foobarbaz.index("f_o_o") == 0
    assert foobarbaz.index("bar") == foobarbaz.index("BAR") == foobarbaz.index("B A R") == 1
    assert foobarbaz.index("baz") == 2

    with pytest.raises(KeyError):
        foobarbaz.index("foobar")


def test_insensitive_set_is_disjoint():
    foobarbaz = InsensitiveSet(("foo", "bar", "FOO", "BAR", "B A Z"))

    assert foobarbaz.isdisjoint({"foobar"})
    assert not foobarbaz.isdisjoint({"baz"})


def test_insensitive_set_is_subset():
    foobarbaz = InsensitiveSet(("foo", "bar", "FOO", "BAR", "B A Z"))
    superset = {"foo", "bar", "BAZ", "foobar"}
    assert foobarbaz.issubset(superset)

    assert foobarbaz < superset
    assert foobarbaz <= superset
    assert not foobarbaz < {"foo", "bar", "BAZ"}


def test_insensitive_set_is_superset():
    foobarbaz = InsensitiveSet(("foo", "bar", "FOO", "BAR", "B A Z"))
    subset = {"Foo", "Bar"}
    assert foobarbaz.issuperset(subset)

    assert foobarbaz > subset
    assert foobarbaz >= subset
    assert not foobarbaz > {"foo", "bar", "BAZ"}


def test_insensitive_set_union():
    foobar = InsensitiveSet(("foo", "bar", "FOO", "BAR"))
    barbaz = {"Bar", "B A Z"}
    assert foobar.union(barbaz) == {"foo", "bar", "B A Z"}
    assert foobar | barbaz == {"foo", "bar", "B A Z"}


def test_insensitive_set_intersection():
    foobar = InsensitiveSet(("foo", "bar", "FOO", "BAR"))
    barbaz = {"Bar", "B A Z"}
    assert foobar.intersection(barbaz) == {"BAR"}
    assert foobar & barbaz == {"BAR"}


def test_insensitive_set_difference():
    foobar = InsensitiveSet(("foo", "bar", "FOO", "BAR"))
    barbaz = {"Bar", "B A Z"}
    assert foobar.difference(barbaz) == {"foo"}
    assert foobar - barbaz == {"foo"}


def test_insensitive_set_symmetric_difference():
    foobar = InsensitiveSet(("foo", "bar", "FOO", "BAR"))
    barbaz = {"Bar", "B A Z"}
    assert foobar.symmetric_difference(barbaz) == {"foo", "B A Z"}
    assert foobar ^ barbaz == {"foo", "B A Z"}


def test_insensitive_set_pop():
    foobar = InsensitiveSet(("foo", "bar", "FOO", " BAR ", "baz"))
    assert foobar.pop() == "baz"
    assert tuple(foobar) == ("foo", "bar")
    assert foobar.pop() == "bar"
    assert tuple(foobar) == ("foo",)
    assert foobar.pop() == "foo"
    assert not foobar

    with pytest.raises(KeyError):
        foobar.pop()


def test_insensitive_set_or_iterable():
    assert tuple(InsensitiveSet(f" {i}" for i in range(8)) | (f"{i} " for i in range(18, 4, -1))) == (
        " 0",
        " 1",
        " 2",
        " 3",
        " 4",
        " 5",
        " 6",
        " 7",
        "18 ",
        "17 ",
        "16 ",
        "15 ",
        "14 ",
        "13 ",
        "12 ",
        "11 ",
        "10 ",
        "9 ",
        "8 ",
    )


def test_insensitive_set_ror_iterable():
    assert tuple((f"{i} " for i in range(18, 4, -1)) | InsensitiveSet(f" {i}" for i in range(8))) == (
        "18 ",
        "17 ",
        "16 ",
        "15 ",
        "14 ",
        "13 ",
        "12 ",
        "11 ",
        "10 ",
        "9 ",
        "8 ",
        "7 ",
        "6 ",
        "5 ",
        " 0",
        " 1",
        " 2",
        " 3",
        " 4",
    )


def test_insensitive_set_and_iterable():
    assert tuple(InsensitiveSet(f" {i}" for i in range(8)) & (f"{i} " for i in range(18, 4, -1))) == (
        " 5",
        " 6",
        " 7",
    )


def test_insensitive_set_rand_iterable():
    assert tuple((f"{i} " for i in range(18, 4, -1)) & InsensitiveSet(f" {i}" for i in range(8))) == (
        "7 ",
        "6 ",
        "5 ",
    )


def test_insensitive_set_xor_iterable():
    assert tuple(InsensitiveSet(f" {i}" for i in range(8)) ^ (f"{i} " for i in range(18, 4, -1))) == (
        " 0",
        " 1",
        " 2",
        " 3",
        " 4",
        "18 ",
        "17 ",
        "16 ",
        "15 ",
        "14 ",
        "13 ",
        "12 ",
        "11 ",
        "10 ",
        "9 ",
        "8 ",
    )


def test_insensitive_set_rxor_iterable():
    assert tuple((f"{i} " for i in range(18, 4, -1)) ^ InsensitiveSet(f" {i}" for i in range(8))) == (
        "18 ",
        "17 ",
        "16 ",
        "15 ",
        "14 ",
        "13 ",
        "12 ",
        "11 ",
        "10 ",
        "9 ",
        "8 ",
        " 0",
        " 1",
        " 2",
        " 3",
        " 4",
    )


def test_insensitive_set_sub_iterable():
    assert tuple(InsensitiveSet(f" {i}" for i in range(8)) - (f"{i} " for i in range(18, 4, -1))) == (
        " 0",
        " 1",
        " 2",
        " 3",
        " 4",
    )


def test_insensitive_set_rsub_iterable():
    assert tuple((f"{i} " for i in range(18, 4, -1)) - InsensitiveSet(f" {i}" for i in range(8))) == (
        "18 ",
        "17 ",
        "16 ",
        "15 ",
        "14 ",
        "13 ",
        "12 ",
        "11 ",
        "10 ",
        "9 ",
        "8 ",
    )


def test_insensitive_set_iand_iterable():
    s = InsensitiveSet(f" {i}" for i in range(8))
    s &= (f"{i} " for i in range(18, 4, -1))

    assert tuple(s) == (
        " 5",
        " 6",
        " 7",
    )


def test_insensitive_set_ior_iterable():
    s = InsensitiveSet(f" {i}" for i in range(8))
    s |= (f"{i} " for i in range(18, 4, -1))

    assert tuple(s) == (
        " 0",
        " 1",
        " 2",
        " 3",
        " 4",
        " 5",
        " 6",
        " 7",
        "18 ",
        "17 ",
        "16 ",
        "15 ",
        "14 ",
        "13 ",
        "12 ",
        "11 ",
        "10 ",
        "9 ",
        "8 ",
    )


def test_insensitive_set_ixor_iterable():
    s = InsensitiveSet(f" {i}" for i in range(8))
    s ^= (f"{i} " for i in range(18, 4, -1))

    assert tuple(s) == (
        " 0",
        " 1",
        " 2",
        " 3",
        " 4",
        "18 ",
        "17 ",
        "16 ",
        "15 ",
        "14 ",
        "13 ",
        "12 ",
        "11 ",
        "10 ",
        "9 ",
        "8 ",
    )


def test_insensitive_set_isub_iterable():
    s = InsensitiveSet(f" {i}" for i in range(8))
    s -= (f"{i} " for i in range(18, 4, -1))

    assert tuple(s) == (
        " 0",
        " 1",
        " 2",
        " 3",
        " 4",
    )


def test_insensitive_set_invalid_inequality():
    with pytest.raises(TypeError):
        InsensitiveSet() <= 1  # noqa: B015

    with pytest.raises(TypeError):
        InsensitiveSet() >= 1  # noqa: B015


def test_insensitive_set_eq_set():
    assert {f" {i}" for i in range(8)} == InsensitiveSet(f"{i} " for i in range(7, -1, -1))
    assert InsensitiveSet(f"{i} " for i in range(7, -1, -1)) == {f" {i}" for i in range(8)}

    assert {f" {i}" for i in range(8)} != InsensitiveSet(f"{i} " for i in range(8, -1, -1))
    assert InsensitiveSet(f"{i} " for i in range(8, -1, -1)) != {f" {i}" for i in range(8)}


def test_insensitive_set_eq_insensitive_set_not_order_sensitive():
    assert InsensitiveSet(f" {i}" for i in range(8)) == InsensitiveSet(f"{i} " for i in range(7, -1, -1))
    assert InsensitiveSet(f" {i}" for i in range(8)) == InsensitiveSet(f"{i} " for i in range(8))
    assert InsensitiveSet(f" {i}" for i in range(8)) != InsensitiveSet(f"{i} " for i in range(7))


def test_insensitive_set_eq_iterable_order_sensitive():
    assert InsensitiveSet(f" {i}" for i in range(8)) != (f"{i} " for i in range(7, -1, -1))
    assert InsensitiveSet(f" {i}" for i in range(8)) == (f"{i} " for i in range(8))


def test_insensitive_set_getitem_positive_int():
    insensitive_set = InsensitiveSet(f" {i}" for i in range(8))
    for i in range(8):
        assert insensitive_set[i] == f" {i}"


def test_insensitive_set_getitem_negative_int():
    insensitive_set = InsensitiveSet(f" {i}" for i in range(8))
    for i, j in zip(range(8), range(-8, 0), strict=True):
        assert insensitive_set[j] == f" {i}"


@pytest.mark.parametrize("start", tuple(range(-5, 4)) + (None,))
@pytest.mark.parametrize("stop", tuple(range(-5, 4)) + (None,))
@pytest.mark.parametrize("step", (-1, 1, None))
def test_insensitive_set_getitem_slices(start, stop, step):
    tup = tuple(f" {i}" for i in range(4))
    iset = InsensitiveSet(tup)

    iset_ret = iset[start:stop:step]
    tup_ret = tup[start:stop:step]

    assert isinstance(iset_ret, InsensitiveSet)
    assert tuple(iset_ret) == tuple(tup_ret)
