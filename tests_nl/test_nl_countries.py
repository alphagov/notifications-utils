import pytest

from notifications_utils.countries.data import (
    ROYAL_MAIL_EUROPEAN,
    UK,
    UK_ISLANDS,
)
from notifications_utils.countries_nl import Country, Postage
from tests_nl.country_synonyms import CROWDSOURCED_MISTAKES


def test_constants():
    assert UK == "United Kingdom"
    assert UK_ISLANDS == [
        ("Alderney", UK),
        ("Brecqhou", UK),
        ("Guernsey", UK),
        ("Herm", UK),
        ("Isle of Man", UK),
        ("Jersey", UK),
        ("Jethou", UK),
        ("Sark", UK),
    ]
    assert Postage.NL == "netherlands"
    assert Postage.EUROPE == "europe"
    assert Postage.REST_OF_WORLD == "rest-of-world"


def test_crowdsourced_test_data():
    for search, expected_country, expected_postage in CROWDSOURCED_MISTAKES:
        if expected_country or expected_postage:
            assert Country(search).canonical_name == expected_country
            assert Country(search).postage_zone == expected_postage


@pytest.mark.parametrize(
    "search, expected",
    (
        ("u.s.a", "rest-of-world"),
        ("Rep of Ireland", "europe"),
        ("deutschland", "europe"),
        ("UK", "rest-of-world"),
        ("Jersey", "rest-of-world"),
        ("Guernsey", "rest-of-world"),
        ("isle-of-man", "rest-of-world"),
        ("ESPAÑA", "europe"),
    ),
)
def test_get_postage(search, expected):
    assert Country(search).postage_zone == expected


def test_euro_postage_zone():
    for search in ROYAL_MAIL_EUROPEAN:
        if search == "Netherlands":
            assert Country(search).postage_zone == Postage.NL
        else:
            assert Country(search).postage_zone == Postage.EUROPE
