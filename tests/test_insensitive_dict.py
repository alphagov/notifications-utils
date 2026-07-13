from functools import partial

import pytest

from notifications_utils.insensitive_dict import (
    ImmutableInsensitiveDict,
    ImmutableInsensitiveSet,
    InsensitiveDict,
    InsensitiveSet,
)
from notifications_utils.recipients import Cell, Row
from notifications_utils.template import SMSPreviewTemplate


@pytest.mark.parametrize("cls", (InsensitiveDict, ImmutableInsensitiveDict))
def test_columns_as_dict_with_keys(cls):
    assert cls({"Date of Birth": "01/01/2001", "TOWN": "London"}).as_dict_with_keys({"date_of_birth", "town"}) == {
        "date_of_birth": "01/01/2001",
        "town": "London",
    }


@pytest.mark.parametrize("cls", (InsensitiveDict, ImmutableInsensitiveDict))
def test_columns_as_dict(cls):
    assert dict(cls({"date of birth": "01/01/2001", "TOWN": "London"})) == {
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
@pytest.mark.parametrize("cls", (InsensitiveDict, ImmutableInsensitiveDict))
def test_lookup(cls, key, should_be_present, in_dictionary):
    assert (key in cls(in_dictionary)) == should_be_present


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
    columns[key_in] = "baz"
    assert columns[lookup_key] == "baz"


def test_immutable_cant_set_item():
    columns = ImmutableInsensitiveDict({})
    with pytest.raises((AttributeError, TypeError)):
        columns["foo"] = "bar"


@pytest.mark.parametrize(
    "key_in",
    [
        "foo",
        "F_O O",
    ],
)
@pytest.mark.parametrize(
    "delete_key",
    [
        "foo",
        "f_o_o",
        "F O O",
    ],
)
def test_del_item(key_in, delete_key):
    columns = InsensitiveDict({key_in: "bar"})
    del columns[delete_key]

    assert delete_key not in columns
    assert key_in not in columns
    assert not columns
    assert len(columns) == 0
    assert tuple(columns.items()) == ()


def test_immutable_cant_del_item():
    columns = ImmutableInsensitiveDict({"foo": "bar", "baz": 123})

    with pytest.raises((AttributeError, TypeError)):
        del columns["foo"]

    with pytest.raises((AttributeError, TypeError)):
        del columns["nonexistent"]


@pytest.mark.parametrize(
    "key_in",
    [
        "foo",
        "F_O O",
    ],
)
@pytest.mark.parametrize(
    "pop_key",
    [
        "foo",
        "f_o_o",
        "F O O",
    ],
)
def test_pop_item(key_in, pop_key):
    columns = InsensitiveDict({key_in: "bar", "baz": 123})
    assert columns.pop(pop_key) == "bar"

    assert pop_key not in columns
    assert key_in not in columns
    assert columns
    assert len(columns) == 1
    assert tuple(columns.items()) == (("baz", 123),)


def test_immutable_cant_pop_item():
    columns = ImmutableInsensitiveDict({"foo": "bar", "baz": 123})

    with pytest.raises((AttributeError, TypeError)):
        columns.pop("foo")

    with pytest.raises((AttributeError, TypeError)):
        columns.pop("nonexistent")


def test_maintains_insertion_order():
    d = InsensitiveDict(
        {
            "B": None,
            "A": None,
            "C": None,
        }
    )
    assert tuple(d.keys()) == ("b", "a", "c")
    d["BB"] = None
    assert tuple(d.keys()) == ("b", "a", "c", "bb")


def test_immutable_maintains_insertion_order():
    d = ImmutableInsensitiveDict(
        {
            "B": None,
            "A": None,
            "C": None,
        }
    )
    assert tuple(d.keys()) == ("b", "a", "c")


def test_update():
    d = InsensitiveDict(
        {
            "A": "A1",
            "B": "B1",
            "C": "C1",
        }
    )
    d.update((("b ", "B2"), ("c ", "C2"), ("d_", "D1"), (" c", "C3")))
    assert tuple(d.items()) == (
        ("a", "A1"),
        ("b", "B2"),
        ("c", "C3"),
        ("d", "D1"),
    )


def test_immutable_cant_update():
    d = ImmutableInsensitiveDict(
        {
            "A": "A1",
            "B": "B1",
            "C": "C1",
        }
    )
    with pytest.raises((AttributeError, TypeError)):
        d.update((("b ", "B2"), ("c ", "C2"), ("d_", "D1"), (" c", "C3")))


@pytest.mark.parametrize("cls", (InsensitiveDict, ImmutableInsensitiveDict))
def test_key_stored_as_normalised_format(cls):
    assert tuple(cls({"foo": 1, "FOO": 2, "f_o_o": 3}).items()) == (("foo", 3),)


@pytest.mark.parametrize("cls", (InsensitiveSet, ImmutableInsensitiveSet))
def test_insensitive_set(cls):
    assert tuple(
        cls(
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


@pytest.mark.parametrize("cls", (InsensitiveSet, ImmutableInsensitiveSet))
def test_insensitive_set_contains(cls):
    foobar = cls(("foo", "bar"))

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


@pytest.mark.parametrize("cls", (InsensitiveSet, ImmutableInsensitiveSet))
def test_insensitive_set_index(cls):
    foobarbaz = cls(("foo", "bar", "FOO", "BAR", "B A Z"))

    assert foobarbaz.index("foo") == foobarbaz.index("FOO") == foobarbaz.index("f_o_o") == 0
    assert foobarbaz.index("bar") == foobarbaz.index("BAR") == foobarbaz.index("B A R") == 1
    assert foobarbaz.index("baz") == 2

    with pytest.raises(KeyError):
        foobarbaz.index("foobar")


@pytest.mark.parametrize("cls", (InsensitiveSet, ImmutableInsensitiveSet))
@pytest.mark.parametrize("other_cls", (InsensitiveSet, ImmutableInsensitiveSet, set))
def test_insensitive_set_is_disjoint(cls, other_cls):
    foobarbaz = InsensitiveSet(("foo", "bar", "FOO", "BAR", "B A Z"))

    assert foobarbaz.isdisjoint(other_cls(("foobar",)))
    assert not foobarbaz.isdisjoint(other_cls(("baz",)))


@pytest.mark.parametrize("cls", (InsensitiveSet, ImmutableInsensitiveSet))
@pytest.mark.parametrize("other_cls", (InsensitiveSet, ImmutableInsensitiveSet, set))
def test_insensitive_set_is_subset(cls, other_cls):
    foobarbaz = cls(("foo", "bar", "FOO", "BAR", "B A Z"))
    superset = other_cls(
        (
            "foo",
            "bar",
            "BAZ",
            "foobar",
        )
    )
    assert foobarbaz.issubset(superset)

    assert foobarbaz < superset
    assert foobarbaz <= superset
    assert not foobarbaz < other_cls(
        (
            "foo",
            "bar",
            "BAZ",
        )
    )


@pytest.mark.parametrize("cls", (InsensitiveSet, ImmutableInsensitiveSet))
@pytest.mark.parametrize("other_cls", (InsensitiveSet, ImmutableInsensitiveSet, set))
def test_insensitive_set_is_superset(cls, other_cls):
    foobarbaz = cls(("foo", "bar", "FOO", "BAR", "B A Z"))
    subset = other_cls(
        (
            "Foo",
            "Bar",
        )
    )
    assert foobarbaz.issuperset(subset)

    assert foobarbaz > subset
    assert foobarbaz >= subset
    assert not foobarbaz > other_cls(
        (
            "foo",
            "bar",
            "BAZ",
        )
    )


@pytest.mark.parametrize("cls", (InsensitiveSet, ImmutableInsensitiveSet))
@pytest.mark.parametrize("other_cls", (InsensitiveSet, ImmutableInsensitiveSet, set))
def test_insensitive_set_union(cls, other_cls):
    foobar = cls(("foo", "bar", "FOO", "BAR"))
    barbaz = other_cls(
        (
            "Bar",
            "B A Z",
        )
    )
    assert foobar.union(barbaz) == {"foo", "bar", "B A Z"}
    assert foobar | barbaz == {"foo", "bar", "B A Z"}


@pytest.mark.parametrize("cls", (InsensitiveSet, ImmutableInsensitiveSet))
@pytest.mark.parametrize("other_cls", (InsensitiveSet, ImmutableInsensitiveSet, set))
def test_insensitive_set_intersection(cls, other_cls):
    foobar = cls(("foo", "bar", "FOO", "BAR"))
    barbaz = other_cls(
        (
            "Bar",
            "B A Z",
        )
    )
    assert foobar.intersection(barbaz) == {"BAR"}
    assert foobar & barbaz == {"BAR"}


@pytest.mark.parametrize("cls", (InsensitiveSet, ImmutableInsensitiveSet))
@pytest.mark.parametrize("other_cls", (InsensitiveSet, ImmutableInsensitiveSet, set))
def test_insensitive_set_difference(cls, other_cls):
    foobar = cls(("foo", "bar", "FOO", "BAR"))
    barbaz = other_cls(
        (
            "Bar",
            "B A Z",
        )
    )
    assert foobar.difference(barbaz) == {"foo"}
    assert foobar - barbaz == {"foo"}


@pytest.mark.parametrize("cls", (InsensitiveSet, ImmutableInsensitiveSet))
@pytest.mark.parametrize("other_cls", (InsensitiveSet, ImmutableInsensitiveSet, set))
def test_insensitive_set_symmetric_difference(cls, other_cls):
    foobar = cls(("foo", "bar", "FOO", "BAR"))
    barbaz = other_cls(
        (
            "Bar",
            "B A Z",
        )
    )
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


def test_immutable_insensitive_set_cant_pop():
    foobar = ImmutableInsensitiveSet(("foo", "bar", "FOO", " BAR ", "baz"))
    with pytest.raises((AttributeError, TypeError)):
        foobar.pop()


@pytest.mark.parametrize("cls", (InsensitiveSet, ImmutableInsensitiveSet))
def test_insensitive_set_or_iterable(cls):
    assert tuple(cls(f" {i}" for i in range(8)) | (f"{i} " for i in range(18, 4, -1))) == (
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


@pytest.mark.parametrize("cls", (InsensitiveSet, ImmutableInsensitiveSet))
def test_insensitive_set_ror_iterable(cls):
    assert tuple((f"{i} " for i in range(18, 4, -1)) | cls(f" {i}" for i in range(8))) == (
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


@pytest.mark.parametrize("cls", (InsensitiveSet, ImmutableInsensitiveSet))
def test_insensitive_set_and_iterable(cls):
    assert tuple(cls(f" {i}" for i in range(8)) & (f"{i} " for i in range(18, 4, -1))) == (
        " 5",
        " 6",
        " 7",
    )


@pytest.mark.parametrize("cls", (InsensitiveSet, ImmutableInsensitiveSet))
def test_insensitive_set_rand_iterable(cls):
    assert tuple((f"{i} " for i in range(18, 4, -1)) & cls(f" {i}" for i in range(8))) == (
        "7 ",
        "6 ",
        "5 ",
    )


@pytest.mark.parametrize("cls", (InsensitiveSet, ImmutableInsensitiveSet))
def test_insensitive_set_xor_iterable(cls):
    assert tuple(cls(f" {i}" for i in range(8)) ^ (f"{i} " for i in range(18, 4, -1))) == (
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


@pytest.mark.parametrize("cls", (InsensitiveSet, ImmutableInsensitiveSet))
def test_insensitive_set_rxor_iterable(cls):
    assert tuple((f"{i} " for i in range(18, 4, -1)) ^ cls(f" {i}" for i in range(8))) == (
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


@pytest.mark.parametrize("cls", (InsensitiveSet, ImmutableInsensitiveSet))
def test_insensitive_set_sub_iterable(cls):
    assert tuple(cls(f" {i}" for i in range(8)) - (f"{i} " for i in range(18, 4, -1))) == (
        " 0",
        " 1",
        " 2",
        " 3",
        " 4",
    )


@pytest.mark.parametrize("cls", (InsensitiveSet, ImmutableInsensitiveSet))
def test_insensitive_set_rsub_iterable(cls):
    assert tuple((f"{i} " for i in range(18, 4, -1)) - cls(f" {i}" for i in range(8))) == (
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


@pytest.mark.parametrize("cls, expect_reassign", ((InsensitiveSet, False), (ImmutableInsensitiveSet, True)))
def test_insensitive_set_iand_iterable(cls, expect_reassign):
    q = s = cls(f" {i}" for i in range(8))
    s &= (f"{i} " for i in range(18, 4, -1))

    assert tuple(s) == (
        " 5",
        " 6",
        " 7",
    )

    assert (q is not s) == expect_reassign


@pytest.mark.parametrize("cls, expect_reassign", ((InsensitiveSet, False), (ImmutableInsensitiveSet, True)))
def test_insensitive_set_ior_iterable(cls, expect_reassign):
    q = s = cls(f" {i}" for i in range(8))
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

    assert (q is not s) == expect_reassign


@pytest.mark.parametrize("cls, expect_reassign", ((InsensitiveSet, False), (ImmutableInsensitiveSet, True)))
def test_insensitive_set_ixor_iterable(cls, expect_reassign):
    q = s = cls(f" {i}" for i in range(8))
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

    assert (q is not s) == expect_reassign


@pytest.mark.parametrize("cls, expect_reassign", ((InsensitiveSet, False), (ImmutableInsensitiveSet, True)))
def test_insensitive_set_isub_iterable(cls, expect_reassign):
    q = s = cls(f" {i}" for i in range(8))
    s -= (f"{i} " for i in range(18, 4, -1))

    assert tuple(s) == (
        " 0",
        " 1",
        " 2",
        " 3",
        " 4",
    )

    assert (q is not s) == expect_reassign


def test_insensitive_set_invalid_inequality():
    with pytest.raises(TypeError):
        InsensitiveSet() <= 1  # noqa: B015

    with pytest.raises(TypeError):
        InsensitiveSet() >= 1  # noqa: B015


@pytest.mark.parametrize("cls", (InsensitiveSet, ImmutableInsensitiveSet))
@pytest.mark.parametrize("other_cls", (InsensitiveSet, ImmutableInsensitiveSet, set))
def test_insensitive_set_eq_set(cls, other_cls):
    assert other_cls(f" {i}" for i in range(8)) == cls(f"{i} " for i in range(7, -1, -1))
    assert cls(f"{i} " for i in range(7, -1, -1)) == other_cls(f" {i}" for i in range(8))

    assert other_cls(f" {i}" for i in range(8)) != cls(f"{i} " for i in range(8, -1, -1))
    assert cls(f"{i} " for i in range(8, -1, -1)) != other_cls(f" {i}" for i in range(8))


@pytest.mark.parametrize("cls", (InsensitiveSet, ImmutableInsensitiveSet))
@pytest.mark.parametrize("other_cls", (InsensitiveSet, ImmutableInsensitiveSet))
def test_insensitive_set_eq_insensitive_set_not_order_sensitive(cls, other_cls):
    assert cls(f" {i}" for i in range(8)) == other_cls(f"{i} " for i in range(7, -1, -1))
    assert cls(f" {i}" for i in range(8)) == other_cls(f"{i} " for i in range(8))
    assert cls(f" {i}" for i in range(8)) != other_cls(f"{i} " for i in range(7))


@pytest.mark.parametrize("cls", (InsensitiveSet, ImmutableInsensitiveSet))
def test_insensitive_set_eq_iterable_order_sensitive(cls):
    assert cls(f" {i}" for i in range(8)) != (f"{i} " for i in range(7, -1, -1))
    assert cls(f" {i}" for i in range(8)) == (f"{i} " for i in range(8))


@pytest.mark.parametrize("cls", (InsensitiveSet, ImmutableInsensitiveSet))
def test_insensitive_set_getitem_positive_int(cls):
    insensitive_set = cls(f" {i}" for i in range(8))
    for i in range(8):
        assert insensitive_set[i] == f" {i}"


@pytest.mark.parametrize("cls", (InsensitiveSet, ImmutableInsensitiveSet))
def test_insensitive_set_getitem_negative_int(cls):
    insensitive_set = cls(f" {i}" for i in range(8))
    for i, j in zip(range(8), range(-8, 0), strict=True):
        assert insensitive_set[j] == f" {i}"


@pytest.mark.parametrize("cls", (InsensitiveSet, ImmutableInsensitiveSet))
@pytest.mark.parametrize("start", tuple(range(-5, 4)) + (None,))
@pytest.mark.parametrize("stop", tuple(range(-5, 4)) + (None,))
@pytest.mark.parametrize("step", (-1, 1, None))
def test_insensitive_set_getitem_slices(cls, start, stop, step):
    tup = tuple(f" {i}" for i in range(4))
    iset = cls(tup)

    iset_ret = iset[start:stop:step]
    tup_ret = tup[start:stop:step]

    assert isinstance(iset_ret, cls)
    assert tuple(iset_ret) == tuple(tup_ret)
