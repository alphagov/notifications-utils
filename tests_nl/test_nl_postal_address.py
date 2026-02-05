import pytest

from notifications_utils.countries_nl import Postage
from notifications_utils.insensitive_dict import InsensitiveDict
from notifications_utils.recipient_validation.notifynl.postal_address import (
    PostalAddress,
    _is_a_real_nl_postcode,
    country_NL,
    format_postcode_for_printing,
)


def test_valid_dutch_address_with_postcode_and_city():
    address = """
    Name and lastname
    Main Street 12
    1234 AB 's-Gravenhage
    """

    pa = PostalAddress(raw_address=address)

    assert pa.postcode == "1234 AB"
    assert pa.city == "'s-Gravenhage"
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
    "raw_address, expected_lines, expected_postcode, expected_city, expected_country, expected_international, expected_valid",  # noqa
    [
        # Dutch address
        (
            """
            name and lastname
            Main Street 12
            1234ab 's-Gravenhage
            Netherlands
            """,
            ["name and lastname", "Main Street 12", "1234 AB  'S-GRAVENHAGE"],
            "1234 AB",
            "'s-Gravenhage",
            "Netherlands",
            False,
            True,
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
            False,  # country def to NL but no correct postcode this should be invalid
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
        ("1234 AB Den Haag", "Den Haag"),
        ("1234ab Amsterdam", "Amsterdam"),
        ("Amsterdam 1234ab", "Amsterdam"),
    ],
)
def test_city_detected_next_to_postcode(line, expected_city):
    pa = PostalAddress(raw_address=f"Some street 1\n{line}")

    assert pa.postcode == "1234 AB"
    assert pa.city == expected_city


def test_city_detected_in_next_line_to_postcode():
    address = """
    Name
    Some Street
    1234 AB
    Den Haag
    Netherlands
    """
    pa = PostalAddress(raw_address=address)
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


@pytest.mark.parametrize(
    "address, expected_international",
    (
        (
            "",
            False,
        ),
        (
            """
                Name
                123 Example Street
                1234 AB City
                Netherlands
            """,
            False,
        ),
        (
            """
                Name
                123 Example Street
                City of Town
                United Kingdom
            """,
            True,
        ),
        (
            """
                Name
                123 Example Street
                City of Town
                Guernsey
            """,
            True,
        ),
        (
            """
                Name
                123 Example Straße
                Deutschland
            """,
            True,
        ),
    ),
)
def test_international(address, expected_international):
    assert PostalAddress(address, allow_international_letters=True).international is expected_international


def test_normalised_lines_for_dutch_address():
    address = """
    Main Street 12
    1234ab Amsterdam
    Netherlands
    """

    pa = PostalAddress(raw_address=address)

    assert pa.normalised_lines == [
        "Main Street 12",
        "1234 AB  AMSTERDAM",
    ]


@pytest.mark.parametrize(
    "address, expected_normalised, expected_as_single_line",
    (
        (
            "",
            "",
            "",
        ),
        (
            """
        Name   LastName   .
        Street    and     Number

        1234  AB   City
        """,
            ("Name LastName.\nStreet and Number\n1234 AB  CITY"),
            ("Name LastName., Street and Number, 1234 AB  CITY"),
        ),
        (
            ("Name LastName. \t  ,    \n, , ,  ,   ,     ,        ,\nStreet and Number, Extra,\n1234 AB City,,\n"),
            ("Name LastName.\nStreet and Number, Extra\n1234 AB  CITY"),
            ("Name LastName., Street and Number, Extra, 1234 AB  CITY"),
        ),
        (
            """
            Name LastName
          123  Example Straße
        Deutschland


        """,
            ("Name LastName\n123 Example Straße\nGermany"),
            ("Name LastName, 123 Example Straße, Germany"),
        ),
    ),
)
def test_normalised(address, expected_normalised, expected_as_single_line):
    assert PostalAddress(address).normalised == expected_normalised
    assert PostalAddress(address).as_single_line == expected_as_single_line


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
        # invalid many spaces postcodes
        ("1234\u00a0\u00a0ab", True),
        ("1234  ab", True),
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


def test_is_a_real_nl_postcode_normalises_before_checking_postcode(mocker):
    normalise_postcode_mock = mocker.patch(
        "notifications_utils.recipient_validation.notifynl.postal_address.normalise_postcode"
    )
    normalise_postcode_mock.return_value = "1234AB"
    assert _is_a_real_nl_postcode("1234 ab") is True


@pytest.mark.parametrize(
    "postcode, postcode_with_space",
    [
        ("1234ab", "1234 AB"),
        ("1234AB", "1234 AB"),
        ("1234 ab", "1234 AB"),
        ("1234  ab", "1234 AB"),
        (" 1234  ab   ", "1234 AB"),
    ],
)
def test_format_postcode_for_printing(postcode, postcode_with_space):
    assert format_postcode_for_printing(postcode) == postcode_with_space


# -----------------------------------------------------
# COUNTRY DETECTION
# -----------------------------------------------------


def test_default_country_is_nl():
    pa = PostalAddress("name \nKalverstraat 1\n1012NX Amsterdam")
    assert pa.country == country_NL


def test_explicit_country_overrides_default():
    pa = PostalAddress("name \nKalverstraat 1\n1012NX\nguatemala", allow_international_letters=True)
    assert pa.country is not country_NL
    assert pa.country.canonical_name == "Guatemala"
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
    assert pa.normalised_lines[-1] == "1012 NX  AMSTERDAM"


def test_normalised_lines_keeps_other_lines():
    pa = PostalAddress("Name\nB\n1012NX Amsterdam")
    assert pa.normalised_lines == ["Name", "B", "1012 NX  AMSTERDAM"]


def test_normalised_lines_keeps_other_lines_and_removes_netherlands():
    pa = PostalAddress("Name\nB\n1012NX Amsterdam\nNetherlands")
    assert pa.normalised_lines == ["Name", "B", "1012 NX  AMSTERDAM"]


@pytest.mark.parametrize(
    "address, result",
    [
        ("name \nStreet 1\n123PC City\nAmerica", "United States"),
        ("name \nStreet 1\n123PC City\nKorea", "South Korea"),
    ],
)
def test_normalised_lines_last_line_with_country(address, result):
    pa = PostalAddress(address, allow_international_letters=True)
    assert pa.normalised_lines[-1] == result


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


@pytest.mark.parametrize(
    "address, expected_personalisation",
    (
        (
            "",
            {
                "address_line_1": "",
                "address_line_2": "",
                "address_line_3": "",
                "address_line_4": "",
                "address_line_5": "",
                "address_line_6": "",
                "postcode": "",
            },
        ),
        (
            """
        name
        123 Example Street
        1234AB City
        """,
            {
                "address_line_1": "name",
                "address_line_2": "123 Example Street",
                "address_line_3": "",
                "address_line_4": "",
                "address_line_5": "",
                "address_line_6": "1234 AB  CITY",
                "postcode": "1234 AB",
            },
        ),
        (
            """
        One
        Two
        Three
        Four
        Five
        Six
        """,
            {
                "address_line_1": "One",
                "address_line_2": "Two",
                "address_line_3": "Three",
                "address_line_4": "Four",
                "address_line_5": "Five",
                "address_line_6": "Six",
                "postcode": "",
            },
        ),
    ),
)
def test_as_personalisation(address, expected_personalisation):
    assert PostalAddress(address).as_personalisation == expected_personalisation


@pytest.mark.parametrize(
    "address",
    [
        (""),
        (
            """
            Example name
            123 Example Street
            1234 AB City
            """
        ),
        (
            """
            User with no Fixed Address,
            1234 AB City
            """
        ),
        (
            """
            A Person
            NFA
            1234 AB Den Haag
            """
        ),
        (
            """
            A Person
            NFA,
            1234 AB Den Haag
            """
        ),
        (
            """
            A Person
            no fixed Abode
            1234 AB Den Haag
            """
        ),
        (
            """
            A Person
            NO FIXED ADDRESS
            1234 AB Den Haag
            """
        ),
        (
            """
            nfa
            1234 AB Den Haag
            Netherlands
            """
        ),
    ],
)
def test_has_no_fixed_abode_address(address):
    assert PostalAddress(address).has_no_fixed_abode_address is False  # NL always returns False for no fixed abode


def test_from_personalisation_handles_int():
    personalisation = {
        "address_line_1": 123,
        "address_line_2": "Example Street",
        "address_line_3": "1234 AB City",
        "address_line_4": "Netherlands",
    }
    assert PostalAddress.from_personalisation(personalisation).normalised == ("123\nExample Street\n1234 AB  CITY")


@pytest.mark.parametrize(
    "address, expected_postage",
    (
        (
            "",
            Postage.NL,
        ),
        (
            """
        Name
        123 Example Street
        1234 AB City of Town
        """,
            Postage.NL,
        ),
        (
            """
            123 Example Street
            City of Town
            Scotland
        """,
            Postage.REST_OF_WORLD,
        ),
        (
            """
            123 Example Straße
            Deutschland
        """,
            Postage.EUROPE,
        ),
        (
            """
        123 Rue Example
        Côte d'Ivoire
        """,
            Postage.REST_OF_WORLD,
        ),
    ),
)
def test_postage(address, expected_postage):
    assert PostalAddress(address).postage == expected_postage


@pytest.mark.parametrize(
    "personalisation",
    (
        {
            "address_line_1": "Name",
            "address_line_3": "123 Example Street",
            "address_line_4": "",
            "postcode": "1234AB City",
            "ignore me": "ignore me",
        },
        {
            "address_line_1": "Name",
            "address_line_3": "123 Example Street",
            "address_line_4": "1234AB City",
        },
        {
            "address_line_2": "Name",
            "address_line_5": "123 Example Street",
            "address_line_6": "1234 AB City",
        },
        {
            "address_line_1": "Name",
            "address_line_3": "123 Example Street",
            "address_line_6": "1234 AB City ",
            "postcode": "ignored if address line 6 provided",
        },
        InsensitiveDict(
            {
                "address_line_1": "Name",
                "address line 2": "123 Example Street",
                "ADDRESS_LINE_3": "",
                "Address-Line-6": "1234  AB City",
            }
        ),
    ),
)
def test_from_personalisation(personalisation):
    assert PostalAddress.from_personalisation(personalisation).normalised == ("Name\n123 Example Street\n1234 AB  CITY")


@pytest.mark.parametrize(
    "address, expected_postcode",
    (
        (
            "",
            None,
        ),
        (
            """
        Name LastName
        123 Example Street
        1234AB City of Town
        """,
            "1234 AB",
        ),
        (
            """
        Name LastName
        123 Example Street
        1234 AB City of Town
        """,
            "1234 AB",
        ),
        (
            """
        Name LastName
        123 Example Straße
        Deutschland
        """,
            None,
        ),
        (
            """
        123 Example Straße
        1234 AB City
        Deutschland
        """,
            None,
        ),
    ),
)
def test_postcode(address, expected_postcode):
    assert PostalAddress(address).has_valid_postcode is bool(expected_postcode)
    assert PostalAddress(address).postcode == expected_postcode


def test_from_personalisation_to_normalisation_doesnt_stringify_nones():
    assert PostalAddress.from_personalisation(
        InsensitiveDict(
            {
                "addressline1": "Notify user",
                "addressline2": "Notifyland",
                "addressline3": None,
                "addressline4": None,
                "addressline5": None,
                "addressline6": "1234 AB City",
            }
        )
    ).normalised_lines == ["Notify user", "Notifyland", "1234 AB  CITY"]


@pytest.mark.parametrize(
    "address",
    (
        """
        Too short, valid postcode
        1234AB City
    """,
        """
        Too short, valid country
        Bhutan
    """,
        """
        Too long, valid postcode
        2
        3
        4
        5
        6
        1234 AB CITY
    """,
        """
        Too long, valid country
        2
        3
        4
        5
        6
        Bhutan
    """,
    ),
)
def test_valid_last_line_too_short_too_long(address):
    postal_address = PostalAddress(address, allow_international_letters=True)
    assert postal_address.valid is False
    assert postal_address.has_valid_last_line is True


@pytest.mark.parametrize(
    "address, international, expected_valid",
    (
        (
            """
            NL Address
            Service can’t send internationally
            1234AB City
        """,
            False,
            True,
        ),
        (
            """
            NL Address
            Service can send internationally
            1234AB City
        """,
            True,
            True,
        ),
        (
            """
            Overseas address
            Service can’t send internationally
            Guinea-Bissau
        """,
            False,
            False,
        ),
        (
            """
            Overseas address
            Service can send internationally
            Guinea-Bissau
        """,
            True,
            True,
        ),
        (
            """
            Overly long address
            2
            3
            4
            5
            6
            7
            8
        """,
            True,
            False,
        ),
        (
            """
            Address too short
            2
        """,
            True,
            False,
        ),
        (
            """
            House
            Service can’t send internationally
            France
        """,
            False,
            False,
        ),
        (
            """
            No postcode or country
            Service can’t send internationally
            3
        """,
            False,
            False,
        ),
        (
            """
            No postcode or country
            Service can send internationally
            3
        """,
            True,
            False,
        ),
        (
            """
            Postcode and country
            Service can’t send internationally
            1234 AB
            France
        """,
            False,
            False,
        ),
    ),
)
def test_valid_with_international_parameter(address, international, expected_valid):
    postal_address = PostalAddress(
        address,
        allow_international_letters=international,
    )
    assert postal_address.valid is expected_valid
    assert postal_address.has_valid_last_line is expected_valid
