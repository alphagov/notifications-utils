import pytest

from notifications_utils.countries import Country
from notifications_utils.countries.data import Postage
from notifications_utils.postal_address import PostalAddress


def test_raw_address():
    raw_address = 'a\n\n\tb\r       c         '
    assert PostalAddress(raw_address).raw_address == raw_address


@pytest.mark.parametrize('address, expected_country', (
    (
        '''
        123 Example Street
        City of Town
        SW1A 1AA
        ''',
        Country('United Kingdom'),
    ),
    (
        '''
        123 Example Street
        City of Town
        SW1A 1AA
        United Kingdom
        ''',
        Country('United Kingdom'),
    ),
    (
        '''
        123 Example Street
        City of Town
        Wales
        ''',
        Country('United Kingdom'),
    ),
    (
        '''
        123 Example Straße
        Deutschland
        ''',
        Country('Germany'),
    ),
))
def test_country(address, expected_country):
    assert PostalAddress(address).country == expected_country


@pytest.mark.parametrize('address, enough_lines_expected', (
    (
        '',
        False,
    ),
    (
        '''
        123 Example Street
        City of Town
        SW1A 1AA
        ''',
        True,
    ),
    (
        '''
        123 Example Street
        City of Town
        United Kingdom
        ''',
        False,
    ),
    (
        '''
        123 Example Street


        City of Town
        ''',
        False,
    ),
    (
        '''
        1
        2
        3
        4
        5
        6
        7
        8
        ''',
        True,
    ),
))
def test_has_enough_lines(address, enough_lines_expected):
    assert PostalAddress(address).has_enough_lines is enough_lines_expected


@pytest.mark.parametrize('address, too_many_lines_expected', (
    (
        '',
        False,
    ),
    (
        '''
        Line 1
        Line 2
        Line 3
        Line 4
        Line 5
        Line 6
        Line 7
        ''',
        False,
    ),
    (
        '''
        Line 1

        Line 2

        Line 3

        Line 4

        Line 5

        Line 6

        Line 7
        ''',
        False,
    ),
    (
        '''
        Line 1
        Line 2
        Line 3
        Line 4
        Line 5
        Line 6
        Line 7
        Scotland
        ''',
        False,
    ),
    (
        '''
        Line 1
        Line 2
        Line 3
        Line 4
        Line 5
        Line 6
        Line 7
        Line 8
        ''',
        True,
    ),
))
def test_has_too_many_lines(address, too_many_lines_expected):
    assert PostalAddress(address).has_too_many_lines is too_many_lines_expected


@pytest.mark.parametrize('address, expected_postcode', (
    (
        '',
        None,
    ),
    (
        '''
        123 Example Street
        City of Town
        SW1A 1AA
        ''',
        'SW1A 1AA'
    ),
    (
        '''
        123 Example Street
        City of Town
        S W1 A 1 AA
        ''',
        'SW1A 1AA'
    ),
    (
        '''
        123 Example Straße
        Deutschland
        ''',
        None,
    ),
))
def test_postcode(address, expected_postcode):
    assert PostalAddress(address).has_valid_postcode is bool(expected_postcode)
    assert PostalAddress(address).postcode == expected_postcode


@pytest.mark.parametrize('address, expected_international', (
    (
        '',
        False,
    ),
    (
        '''
        123 Example Street
        City of Town
        SW1A 1AA
        ''',
        False,
    ),
    (
        '''
        123 Example Street
        City of Town
        United Kingdom
        ''',
        False,
    ),
    (
        '''
        123 Example Street
        City of Town
        Guernsey
        ''',
        False,
    ),
    (
        '''
        123 Example Straße
        Deutschland
        ''',
        True,
    ),
))
def test_international(address, expected_international):
    assert PostalAddress(address).international is expected_international


@pytest.mark.parametrize('address, expected_normalised', (
    (
        '',
        '',
    ),
    (
        '''
        123 Example    St  .
        City    of Town

        S W1 A 1 AA
        ''',
        (
            '123 Example St.\n'
            'City of Town\n'
            'SW1A 1AA'
        ),
    ),
    (
        '''
          123  Example Straße
        Deutschland


        ''',
        (
            '123 Example Straße\n'
            'Germany'
        ),
    ),
))
def test_normalised(address, expected_normalised):
    assert PostalAddress(address).normalised == expected_normalised


@pytest.mark.parametrize('address, expected_postage', (
    (
        '',
        Postage.UK,
    ),
    (
        '''
        123 Example Street
        City of Town
        SW1A 1AA
        ''',
        Postage.UK,
    ),
    (
        '''
        123 Example Street
        City of Town
        Scotland
        ''',
        Postage.UK,
    ),
    (
        '''
        123 Example Straße
        Deutschland
        ''',
        Postage.EUROPE,
    ),
    (
        '''
        123 Rue Example
        Côte d'Ivoire
        ''',
        Postage.REST_OF_WORLD,
    ),
))
def test_postage(address, expected_postage):
    assert PostalAddress(address).postage == expected_postage
