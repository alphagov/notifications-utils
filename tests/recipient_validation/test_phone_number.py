import pytest

from notifications_utils.recipient_validation.errors import InvalidPhoneError
from notifications_utils.recipient_validation.phone_number import (
    format_phone_number_human_readable,
    get_international_phone_info,
    international_phone_info,
    is_uk_phone_number,
    normalise_phone_number,
    try_validate_and_format_phone_number,
    validate_and_format_phone_number,
    validate_phone_number,
)
from notifications_utils.recipients import (
    allowed_to_send_to,
    format_recipient,
)

valid_uk_mobile_phone_numbers = [
    "7123456789",
    "07123456789",
    "07123 456789",
    "07123-456-789",
    "00447123456789",
    "00 44 7123456789",
    "+447123456789",
    "+44 7123 456 789",
    "+44 (0)7123 456 789",
    "\u200b\t\t+44 (0)7123 \ufeff 456 789 \r\n",
]


valid_international_phone_numbers = [
    "71234567890",  # Russia
    "1-202-555-0104",  # USA
    "+12025550104",  # USA
    "0012025550104",  # USA
    "+0012025550104",  # USA
    "23051234567",  # Mauritius,
    "+682 12345",  # Cook islands
    "+3312345678",
    "003312345678",
    "1-2345-12345-12345",  # 15 digits
]


valid_mobile_phone_numbers = valid_uk_mobile_phone_numbers + valid_international_phone_numbers

valid_uk_landlines = [
    "0117 496 0860",  # regular uk landline
    "0044 117 496 0860",
    "44 117 496 0860",
    "+44 117 496 0860",
    "016064 1234",  # brampton (one digit shorter than normal)
    "020 7946 0991",  # london
    "030 1234 5678",  # non-geographic
    "0500 123 4567",  # corporate numbering and voip services
    "0800 123 4567",  # freephone
    "0800 123 456",  # shorter freephone
    "0800 11 11",  # shortest freephone
    "0845 46 46",  # short premium
    "0900 123 4567",  # premium
]

invalid_uk_landlines = [
    "0400 123 4567",  # not in use
    "0600 123 4567",  # not in use
    "0300 46 46",  # short but not 01x or 08x
    "0800 11 12",  # short but not 01x or 08x
    "0845 46 31",  # short but not 01x or 08x
]

invalid_uk_mobile_phone_numbers = sum(
    [
        [(phone_number, error) for phone_number in group]
        for error, group in [
            (
                "Mobile number is too long",
                (
                    "712345678910",
                    "0712345678910",
                    "0044712345678910",
                    "0044712345678910",
                    "+44 (0)7123 456 789 10",
                ),
            ),
            (
                "Mobile number is too short",
                (
                    "0712345678",
                    "004471234567",
                    "00447123456",
                    "+44 (0)7123 456 78",
                ),
            ),
            (
                "This does not look like a UK mobile number – double check the mobile number you entered",
                valid_uk_landlines + invalid_uk_landlines,
            ),
            (
                "Mobile numbers can only include: 0 1 2 3 4 5 6 7 8 9 ( ) + -",
                (
                    "07890x32109",
                    "07123 456789...",
                    "07123 ☟☜⬇⬆☞☝",
                    "07123☟☜⬇⬆☞☝",
                    '07";DROP TABLE;"',
                    "+44 07ab cde fgh",
                    "ALPHANUM3R1C",
                ),
            ),
        ]
    ],
    [],
)


invalid_mobile_phone_numbers = list(
    filter(
        lambda number: number[0]
        not in {
            "712345678910",  # Could be Russia
        },
        invalid_uk_mobile_phone_numbers,
    )
) + [
    ("80000000000", "Country code not found - double check the mobile number you entered"),
    ("1234567", "Mobile number is too short"),
    ("+682 1234", "Mobile number is too short"),  # Cook Islands phone numbers can be 5 digits
    ("+12345 12345 12345 6", "Mobile number is too long"),
]


@pytest.mark.parametrize("phone_number", valid_international_phone_numbers)
def test_detect_international_phone_numbers(phone_number):
    assert is_uk_phone_number(phone_number) is False


@pytest.mark.parametrize("phone_number", valid_uk_mobile_phone_numbers)
def test_detect_uk_phone_numbers(phone_number):
    assert is_uk_phone_number(phone_number) is True


@pytest.mark.parametrize(
    "phone_number, expected_info",
    [
        (
            "07900900123",
            international_phone_info(
                international=False,
                crown_dependency=False,
                country_prefix="44",  # UK
                billable_units=1,
            ),
        ),
        (
            "07700900123",
            international_phone_info(
                international=False,
                crown_dependency=False,
                country_prefix="44",  # Number in TV range
                billable_units=1,
            ),
        ),
        (
            "07700800123",
            international_phone_info(
                international=True,
                crown_dependency=True,
                country_prefix="44",  # UK Crown dependency, so prefix same as UK
                billable_units=1,
            ),
        ),
        (
            "20-12-1234-1234",
            international_phone_info(
                international=True,
                crown_dependency=False,
                country_prefix="20",  # Egypt
                billable_units=3,
            ),
        ),
        (
            "00201212341234",
            international_phone_info(
                international=True,
                crown_dependency=False,
                country_prefix="20",  # Egypt
                billable_units=3,
            ),
        ),
        (
            "1664000000000",
            international_phone_info(
                international=True,
                crown_dependency=False,
                country_prefix="1664",  # Montserrat
                billable_units=3,
            ),
        ),
        (
            "71234567890",
            international_phone_info(
                international=True,
                crown_dependency=False,
                country_prefix="7",  # Russia
                billable_units=4,
            ),
        ),
        (
            "1-202-555-0104",
            international_phone_info(
                international=True,
                crown_dependency=False,
                country_prefix="1",  # USA
                billable_units=1,
            ),
        ),
        (
            "+23051234567",
            international_phone_info(
                international=True,
                crown_dependency=False,
                country_prefix="230",  # Mauritius
                billable_units=2,
            ),
        ),
    ],
)
def test_get_international_info(phone_number, expected_info):
    assert get_international_phone_info(phone_number) == expected_info


@pytest.mark.parametrize(
    "phone_number",
    [
        "abcd",
        "079OO900123",
        pytest.param("", marks=pytest.mark.xfail),
        pytest.param("12345", marks=pytest.mark.xfail),
        pytest.param("+12345", marks=pytest.mark.xfail),
        pytest.param("1-2-3-4-5", marks=pytest.mark.xfail),
        pytest.param("1 2 3 4 5", marks=pytest.mark.xfail),
        pytest.param("(1)2345", marks=pytest.mark.xfail),
    ],
)
def test_normalise_phone_number_raises_if_unparseable_characters(phone_number):
    with pytest.raises(InvalidPhoneError):
        normalise_phone_number(phone_number)


@pytest.mark.parametrize(
    "phone_number",
    [
        "+21 4321 0987",
        "00997 1234 7890",
        "801234-7890",
        "(8-0)-1234-7890",
    ],
)
def test_get_international_info_raises(phone_number):
    with pytest.raises(InvalidPhoneError) as error:
        get_international_phone_info(phone_number)
    assert str(error.value) == "Country code not found - double check the mobile number you entered"


@pytest.mark.parametrize("phone_number", valid_uk_mobile_phone_numbers)
@pytest.mark.parametrize(
    "extra_args",
    [
        {},
        {"international": False},
    ],
)
def test_phone_number_accepts_valid_values(extra_args, phone_number):
    try:
        validate_phone_number(phone_number, **extra_args)
    except InvalidPhoneError:
        pytest.fail("Unexpected InvalidPhoneError")


@pytest.mark.parametrize("phone_number", valid_mobile_phone_numbers)
def test_phone_number_accepts_valid_international_values(phone_number):
    try:
        validate_phone_number(phone_number, international=True)
    except InvalidPhoneError:
        pytest.fail("Unexpected InvalidPhoneError")


@pytest.mark.parametrize("phone_number", valid_uk_mobile_phone_numbers)
def test_valid_uk_phone_number_can_be_formatted_consistently(phone_number):
    assert validate_and_format_phone_number(phone_number) == "447123456789"


@pytest.mark.parametrize(
    "phone_number, expected_formatted",
    [
        ("71234567890", "71234567890"),
        ("1-202-555-0104", "12025550104"),
        ("+12025550104", "12025550104"),
        ("0012025550104", "12025550104"),
        ("+0012025550104", "12025550104"),
        ("23051234567", "23051234567"),
    ],
)
def test_valid_international_phone_number_can_be_formatted_consistently(phone_number, expected_formatted):
    assert validate_and_format_phone_number(phone_number, international=True) == expected_formatted


@pytest.mark.parametrize("phone_number, error_message", invalid_uk_mobile_phone_numbers)
@pytest.mark.parametrize(
    "extra_args",
    [
        {},
        {"international": False},
    ],
)
def test_phone_number_rejects_invalid_values(extra_args, phone_number, error_message):
    with pytest.raises(InvalidPhoneError) as e:
        validate_phone_number(phone_number, **extra_args)
    assert error_message == str(e.value)


@pytest.mark.parametrize("phone_number, error_message", invalid_mobile_phone_numbers)
def test_phone_number_rejects_invalid_international_values(phone_number, error_message):
    with pytest.raises(InvalidPhoneError) as e:
        validate_phone_number(phone_number, international=True)
    assert error_message == str(e.value)


@pytest.mark.parametrize("phone_number", valid_uk_mobile_phone_numbers)
def test_validates_against_guestlist_of_phone_numbers(phone_number):
    assert allowed_to_send_to(phone_number, ["07123456789", "07700900460", "test@example.com"])
    assert not allowed_to_send_to(phone_number, ["07700900460", "07700900461", "test@example.com"])


@pytest.mark.parametrize(
    "recipient_number, allowlist_number",
    [
        ["1-202-555-0104", "0012025550104"],
        ["0012025550104", "1-202-555-0104"],
    ],
)
def test_validates_against_guestlist_of_international_phone_numbers(recipient_number, allowlist_number):
    assert allowed_to_send_to(recipient_number, [allowlist_number])


@pytest.mark.parametrize(
    "phone_number, expected_formatted",
    [
        ("07900900123", "07900 900123"),  # UK
        ("+44(0)7900900123", "07900 900123"),  # UK
        ("447900900123", "07900 900123"),  # UK
        ("20-12-1234-1234", "+20 12 12341234"),  # Egypt
        ("00201212341234", "+20 12 12341234"),  # Egypt
        ("1664 0000000", "+1 664-000-0000"),  # Montserrat
        ("7 499 1231212", "+7 499 123-12-12"),  # Moscow (Russia)
        ("1-202-555-0104", "+1 202-555-0104"),  # Washington DC (USA)
        ("+23051234567", "+230 5123 4567"),  # Mauritius
        ("33(0)1 12345678", "+33 1 12 34 56 78"),  # Paris (France)
    ],
)
def test_format_uk_and_international_phone_numbers(phone_number, expected_formatted):
    assert format_phone_number_human_readable(phone_number) == expected_formatted


@pytest.mark.parametrize(
    "recipient, expected_formatted",
    [
        (True, ""),
        (False, ""),
        (0, ""),
        (0.1, ""),
        (None, ""),
        ("foo", "foo"),
        ("TeSt@ExAmPl3.com", "test@exampl3.com"),
        ("+4407900 900 123", "447900900123"),
        ("+1 800 555 5555", "18005555555"),
    ],
)
def test_format_recipient(recipient, expected_formatted):
    assert format_recipient(recipient) == expected_formatted


def test_try_format_recipient_doesnt_throw():
    assert try_validate_and_format_phone_number("ALPHANUM3R1C") == "ALPHANUM3R1C"


def test_format_phone_number_human_readable_doenst_throw():
    assert format_phone_number_human_readable("ALPHANUM3R1C") == "ALPHANUM3R1C"
