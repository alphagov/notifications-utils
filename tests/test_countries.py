import pytest

from notifications_utils.countries import (
    Country,
    CountryNotFoundError
)
from notifications_utils.countries.data import (
    ADDITIONAL_SYNONYMS,
    ROYAL_MAIL_EUROPEAN,
    UK,
    UK_ISLANDS,
    Postage,
)
from .country_synonyms import ALL as ALL_SYNONYMS


def test_constants():
    assert UK == 'United Kingdom'
    assert UK_ISLANDS == [
        ('Jersey', 'Jersey'),
        ('Guernsey', 'Guernsey'),
        ('Isle of Man', 'Isle of Man'),
    ]
    assert Postage.EUROPE == 'Europe'
    assert Postage.REST_OF_WORLD == 'rest of world'
    assert Postage.UK == 'United Kingdom'


@pytest.mark.parametrize('synonym, canonical', ADDITIONAL_SYNONYMS)
def test_hand_crafted_synonyms_map_to_canonical_countries(synonym, canonical):
    assert Country(canonical).canonical_name == canonical
    assert Country(synonym).canonical_name == canonical


def test_all_synonyms():
    for search, expected in ALL_SYNONYMS:
        assert Country(search).canonical_name == expected


@pytest.mark.parametrize('search, expected', (
    ('u.s.a', 'United States'),
    ('america', 'United States'),
    ('United States America', 'United States'),
    ('ROI', 'Ireland'),
    ('Irish Republic', 'Ireland'),
    ('Rep of Ireland', 'Ireland'),
    ('RepOfIreland', 'Ireland'),
    ('deutschland', 'Germany'),
    ('UK', 'United Kingdom'),
    ('England', 'United Kingdom'),
    ('Northern Ireland', 'United Kingdom'),
    ('Scotland', 'United Kingdom'),
    ('Wales', 'United Kingdom'),
    ('N. Ireland', 'United Kingdom'),
    ('GB', 'United Kingdom'),
    ('NIR', 'United Kingdom'),
    ('SCT', 'United Kingdom'),
    ('WLS', 'United Kingdom'),
    ('gambia', 'The Gambia'),
    ('Jersey', 'Jersey'),
    ('Guernsey', 'Guernsey'),
    ('Lubnān', 'Lebanon'),
    ('Lubnan', 'Lebanon'),
    ('ESPAÑA', 'Spain'),
    ('ESPANA', 'Spain'),
    ("the democratic people's republic of korea", 'North Korea'),
    ("the democratic peoples republic of korea", 'North Korea'),
    ('ALAND', 'Åland Islands'),
    ('Sao Tome + Principe', 'Sao Tome and Principe'),
    ('Sao Tome & Principe', 'Sao Tome and Principe'),
    ('Antigua, and Barbuda', 'Antigua and Barbuda'),
    ('Azores', 'Azores'),
    ('Autonomous Region of the Azores', 'Azores'),
    ('Canary Islands', 'Canary Islands'),
    ('Islas Canarias', 'Canary Islands'),
    ('Canaries', 'Canary Islands'),
    ('Madeira', 'Madeira'),
    ('Autonomous Region of Madeira', 'Madeira'),
    ('Região Autónoma da Madeira', 'Madeira'),
    ('Balearic Islands', 'Balearic Islands'),
    ('Islas Baleares', 'Balearic Islands'),
    ('Illes Balears', 'Balearic Islands'),
    ('Corsica', 'Corsica'),
    ('Corse', 'Corsica'),
))
def test_hand_crafted_synonyms(search, expected):
    assert Country(search).canonical_name == expected


@pytest.mark.parametrize('search', (
    'Qumran',
    'Kumrahn',
))
def test_non_existant_countries(search):
    with pytest.raises(KeyError):
        Country(search)
    with pytest.raises(CountryNotFoundError) as error:
        Country(search)
        assert str(error) == 'foo'


@pytest.mark.parametrize('search, expected', (
    ('u.s.a', 'rest of world'),
    ('Rep of Ireland', 'Europe'),
    ('deutschland', 'Europe'),
    ('UK', 'United Kingdom'),
    ('Jersey', 'United Kingdom'),
    ('Guernsey', 'United Kingdom'),
    ('isle-of-man', 'United Kingdom'),
    ('ESPAÑA', 'Europe'),
))
def test_get_postage(search, expected):
    assert Country(search).postage_zone == expected


def test_euro_postage_zone():
    for search in ROYAL_MAIL_EUROPEAN:
        assert Country(search).postage_zone == Postage.EUROPE
