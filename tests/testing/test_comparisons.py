import re

from notifications_utils.testing.comparisons import (
    AnyStringMatching,
    AnySupersetOf,
    ExactIdentity,
    RestrictedAny,
)


class TestRestrictedAny:
    def test_any_odd(self):
        any_odd = RestrictedAny(lambda x: x % 2)
        assert (
            4,
            5,
            6,
        ) == (
            4,
            any_odd,
            6,
        )
        assert (
            4,
            9,
            6,
        ) == (
            4,
            any_odd,
            6,
        )
        assert not (
            4,
            9,
            6,
        ) == (
            4,
            any_odd,
            any_odd,
        )


class TestAnySupersetOf:
    def test_superset(self):
        assert [{"a": 123, "b": 456, "less": "predictabananas"}, 789] == [AnySupersetOf({"a": 123, "b": 456}), 789]


class TestStringMatching:
    def test_string_matching(self):
        assert {"a": "Metempsychosis", "b": "c"} == {"a": AnyStringMatching(r"m+.+psycho.*", flags=re.I), "b": "c"}

    def test_pattern_caching(self):
        # not actually testing that it *is* definitely caching, just checking that it's not broken due to attempted
        # caching
        pattern_a = AnyStringMatching(r"transmigration", flags=re.I)
        pattern_b = AnyStringMatching(r"transmigration")
        pattern_c = AnyStringMatching(r"transmigration", flags=re.I)
        pattern_d = AnyStringMatching(r"Transmigration", flags=re.I)
        pattern_e = AnyStringMatching(r"Transmigration")
        pattern_f = AnyStringMatching(r"transmigration")

        assert {
            "u": "transMigration",
            "v": "transmigration",
            "w": "Transmigration",
            "x": "transmigratioN",
            "y": "Transmigration",
            "z": "transmigration",
        } == {
            "u": pattern_a,
            "v": pattern_b,
            "w": pattern_c,
            "x": pattern_d,
            "y": pattern_e,
            "z": pattern_f,
        }

        assert {
            "u": "transMigration",
            "v": "transmigration",
            "w": "Transmigration",
            "x": "transmigratioN",
            "y": "Transmigration",
            "z": "Transmigration",  # <-- only difference here
        } != {
            "u": pattern_a,
            "v": pattern_b,
            "w": pattern_c,
            "x": pattern_d,
            "y": pattern_e,
            "z": pattern_f,
        }


class TestExactIdentity:
    def test_exact_identity(self):
        x = []
        assert (
            7,
            ExactIdentity(x),
        ) == (
            7,
            x,
        )
        assert not (
            7,
            ExactIdentity(x),
        ) == (
            7,
            [],
        )
