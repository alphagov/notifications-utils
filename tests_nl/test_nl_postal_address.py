import pytest

from notifications_utils.countries_nl import Postage
from notifications_utils.recipient_validation.notifynl.postal_address import (
    PostalAddress,
    _is_a_real_nl_postcode,
    country_NL,
)


def test_valid_dutch_address_with_postcode_and_city():
    address = """
    Name and lastname
    Main Street 12
    1234 AB Amsterdam
    """

    pa = PostalAddress(raw_address=address)

    assert pa.postcode == "1234 AB"
    assert pa.city == "Amsterdam"
    assert pa.country.canonical_name == "Netherlands"
    assert pa.postage == Postage.NL
    assert pa.international is False
    assert pa.valid is True


def test_allow_international_letters():
    address = """
    First Lastname
    123 Example St
    Fiji
    """

    pa = PostalAddress(raw_address=address, allow_international_letters=False)
    assert pa.valid is False

    pa = PostalAddress(raw_address=address, allow_international_letters=True)
    assert pa.valid is True


@pytest.mark.parametrize(
    "raw_address, expected_lines, expected_postcode, expected_city, expected_country, expected_international, expected_valid",  # noqa: E501
    [
        # Dutch address
        (
            """
            name and lastname
            Main Street 12
            1234ab Amsterdam
            Netherlands
            """,
            ["name and lastname", "Main Street 12", "1234 AB\u00a0\u00a0Amsterdam"],
            "1234 AB",
            "Amsterdam",
            "Netherlands",
            False,
            True,
        ),
        (
            """
            name and lastname
            Main Street 12
            12ab Amsterdam
            Netherlands
            """,
            ["name and lastname", "Main Street 12", "12ab Amsterdam", "Netherlands"],
            None,
            None,
            "Netherlands",
            False,
            False,
        ),
        # International address
        (
            """
            name and lastname
            Baker Street 221B
            London
            United Kingdom
            """,
            ["name and lastname", "Baker Street 221B", "London", "United Kingdom"],
            None,
            None,
            "United Kingdom",
            True,
            True,
        ),
        (
            """
            name and lastname
            Baker Street 221B
            London
            """,
            ["name and lastname", "Baker Street 221B", "London"],
            None,
            None,
            "Netherlands",  # no country found defaults to NL
            False,
            False,
        ),
    ],
)
def test_normalised_lines_for_addresses(
    raw_address,
    expected_lines,
    expected_postcode,
    expected_city,
    expected_country,
    expected_international,
    expected_valid,
):
    pa = PostalAddress(raw_address=raw_address, allow_international_letters=True)

    assert pa.normalised_lines == expected_lines
    assert pa.postcode == expected_postcode
    assert pa.city == expected_city
    assert pa.country.canonical_name == expected_country
    assert pa.international is expected_international
    assert pa.valid is expected_valid


@pytest.mark.parametrize(
    "line, expected_city",
    [
        ("Amsterdam 1234 AB", "Amsterdam"),
        ("1234 AB Amsterdam", "Amsterdam"),
        ("1234ab Amsterdam", "Amsterdam"),
        ("Amsterdam 1234ab", "Amsterdam"),
    ],
)
def test_city_detected_next_to_postcode(line, expected_city):
    pa = PostalAddress(raw_address=f"Some street 1\n{line}")

    assert pa.postcode == "1234 AB"
    assert pa.city == expected_city


def test_city_detected_in_next_line_to_postcode():
    pa = PostalAddress(raw_address="Name\nSome street 1\n1234AB\nDen Haag\nNederland")
    assert pa.postcode == "1234 AB"
    assert pa.city == "Den Haag"
    assert pa.valid is True


def test_international_address_with_country_last_line():
    address = """
    Baker Street 221B
    London
    United Kingdom
    """

    pa = PostalAddress(raw_address=address, allow_international_letters=True)

    assert pa.international is True
    assert pa.postcode is None
    assert pa.city is None
    assert pa.country.canonical_name == "United Kingdom"
    assert pa.valid is True


def test_normalised_lines_for_dutch_address():
    address = """
    Main Street 12
    1234ab Amsterdam
    Netherlands
    """

    pa = PostalAddress(raw_address=address)

    assert pa.normalised_lines == [
        "Main Street 12",
        "1234 AB\u00a0\u00a0Amsterdam",
    ]


def test_invalid_characters_in_address_line():
    address = """
    @Main Street 12
    1234 AB Amsterdam
    """

    pa = PostalAddress(raw_address=address)

    assert pa.has_invalid_characters is True
    assert pa.valid is False


# -----------------------------------------------------
# BASIC POSTCODE PARSING
# -----------------------------------------------------


@pytest.fixture(
    params=[
        ("name \nKalverstraat 1\n1012NX Amsterdam", "1012 NX", "Amsterdam"),
        ("name \nKalverstraat 1\n1012 nx Den Haag", "1012 NX", "Den Haag"),
        ("name \nKalverstraat 1\n1012  NX Almere", "1012 NX", "Almere"),
        (["name", "Kalverstraat 1", "1012NX Rotterdam"], "1012 NX", "Rotterdam"),
    ]
)
def nl_address_case(request):
    return request.param


def test_nl_postcode_parsing(nl_address_case):
    address, postcode, city = nl_address_case
    pa = PostalAddress(address)
    assert pa.postcode == postcode
    assert pa.city == city


@pytest.mark.parametrize(
    "postcode, result",
    [
        # real standard UK poscodes
        ("1234 AB", True),
        ("1234AB", True),
        ("1234 ab", True),
        ("1234ab", True),
        # invalid / half line postcodes
        ("1234\u00a0ab", False),
        # invalid / incomplete postcodes
        ("N5", False),
        ("SO144 6WB", False),
        ("SO14 6WBA", False),
        ("NF1 1AA", False),
        ("", False),
        ("Bad postcode", False),
        # British Forces Post Office numbers are not postcodes
        ("BFPO1234", False),
        ("BFPO C/O 1234", False),
        ("BFPO 1234", False),
        ("BFPO1", False),
        ("BFPO", False),
        ("BFPO12345", False),
        # Europe postal zone
        ("GX111AA", False),
    ],
)
def test_if_postcode_is_a_real_nl_postcode(postcode, result):
    assert _is_a_real_nl_postcode(postcode) is result


# -----------------------------------------------------
# COUNTRY DETECTION
# -----------------------------------------------------


def test_default_country_is_nl():
    pa = PostalAddress("name \nKalverstraat 1\n1012NX Amsterdam")
    assert pa.country == country_NL


def test_explicit_country_overrides_default():
    pa = PostalAddress("name \nKalverstraat 1\n1012NX\nRussia", allow_international_letters=True)
    assert pa.country is not country_NL
    assert pa.country.canonical_name == "Russia"
    assert pa.valid is True


def test_unknown_explicit_country_returns_default_and_valid():
    pa = PostalAddress("name \nKalverstraat 1\n1012NX Amsterdam\nNotACountry", allow_international_letters=True)
    assert pa.country == country_NL
    assert pa.valid is True


def test_unknown_country_and_postcode_returns_invalid():
    pa = PostalAddress("name \nKalverstraat 1\n10NX Amsterdam\nNotACountry")
    assert pa.valid is False


# -----------------------------------------------------
# NORMALISATION
# -----------------------------------------------------


def test_normalised_lines_replaces_last_line_with_postcode():
    pa = PostalAddress("name \nKalverstraat 1\n1012nx Amsterdam")
    assert pa.normalised_lines[-1] == "1012 NX\u00a0\u00a0Amsterdam"


def test_normalised_lines_keeps_other_lines():
    pa = PostalAddress("Name\nB\n1012NX Amsterdam")
    assert pa.normalised_lines == ["Name", "B", "1012 NX\u00a0\u00a0Amsterdam"]


# -----------------------------------------------------
# VALIDATION RULES
# -----------------------------------------------------


def test_valid_address():
    pa = PostalAddress("name\nKalverstraat 1\n1012NX Amsterdam")
    assert pa.valid is True


def test_invalid_without_postcode():
    pa = PostalAddress("name\nKalverstraat 1\nAmsterdam")
    assert pa.valid is False


def test_too_few_lines():
    pa = PostalAddress("1012NX Den Haag")
    assert pa.has_enough_lines is False
    assert pa.valid is False


def test_too_many_lines():
    pa = PostalAddress("\n".join(["Line1", "Line2", "Line3", "Line4", "Line5", "Line6", "Line7", "1012NX"]))
    assert pa.has_too_many_lines is True
    assert pa.valid is False


# -----------------------------------------------------
# INVALID CHARACTERS
# -----------------------------------------------------


@pytest.mark.parametrize(
    "line",
    [
        "@Weird start",
        "(Bad format street",
        "[Bracket street",
    ],
)
def test_invalid_characters(line):
    pa = PostalAddress(f"{line}\n street \n1012NX Amsterdam")
    assert pa.has_invalid_characters is True
    assert pa.valid is False


# -----------------------------------------------------
# SPECIAL CASES
# -----------------------------------------------------


def test_address_as_list():
    pa = PostalAddress(["name \nKalverstraat 1", "1012NX Amsterdam"])
    assert pa.postcode == "1012 NX"
    assert pa.valid is True


def test_mixed_case_and_spacing():
    pa = PostalAddress("name \nKalverstraat 1 \n  1012  nx   Amsterdam  ")
    assert pa.postcode == "1012 NX"
    assert pa.city == "Amsterdam"
    assert pa.valid is True


def test_does_not_treat_bfpo_as_special():
    pa = PostalAddress("name \nBFPO 123\n1012NX Amsterdam")
    # UK class would mark this as BFPO; NL must ignore
    assert not getattr(pa, "is_bfpo_address", False)
    assert pa.postcode == "1012 NX"
    assert pa.valid is True
