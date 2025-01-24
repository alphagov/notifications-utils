import pytest

from notifications_utils.recipient_validation.errors import InvalidPhoneError
from notifications_utils.recipient_validation.phone_number import PhoneNumber, international_phone_info
from notifications_utils.recipients import (
    allowed_to_send_to,
    format_recipient,
)

valid_uk_mobile_phone_numbers = [
    "7723456789",
    "07723456789",
    "07723 456789",
    "07723-456-789",
    "00447723456789",
    "00 44 7723456789",
    "+447723456789",
    "+44 7723 456 789",
    "+44 (0)7723 456 789",
    "\u200b\t\t+44 (0)7723 456 789\ufeff \r\n",
]


valid_international_phone_numbers = [
    "+7 (8) (495) 123-45-67",  # russia
    "007 (8) (495) 123-45-67",  # russia
    "784951234567",  # Russia but without a + or 00 so it looks like it could be a uk phone number
    "1-202-555-0104",  # USA
    "+12025550104",  # USA
    "0012025550104",  # USA
    "+0012025550104",  # USA
    "230 5 2512345",  # Mauritius
    "+682 50 123",  # Cook islands
    "+33122334455",  # France
    "0033122334455",  # France
    "+43 676 111 222 333 4",  # Austrian 13 digit phone numbers
]

# placeholder to be removed when the old validation code is removed
# categorising these numbers as international numbers will cause old checks
# for uk numbers to fail
valid_channel_island_numbers = [
    "+447797292290",  # Jersey
    "+447797333214",  # Jersey
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
    "0550 123 4567",  # corporate numbering and voip services
]

invalid_uk_landlines = [
    "0400 123 4567",  # not in use
    "0600 123 4567",  # not in use
    "0300 46 46",  # short but not 01x or 08x
    "0800 11 12",  # short but not 01x or 08x
    "0845 46 31",  # short but not 01x or 08x
    "0845 46 46",  # short premium
    "0900 123 4567",  # premium
]

invalid_uk_mobile_phone_numbers = sum(
    [
        [(phone_number, error) for phone_number in group]
        for error, group in [
            (
                InvalidPhoneError.ERROR_MESSAGES[InvalidPhoneError.Codes.TOO_LONG],
                (
                    "772345678910",
                    "0772345678910",
                    "0044772345678910",
                    "0044772345678910",
                    "+44 (0)7723 456 789 10",
                ),
            ),
            (
                InvalidPhoneError.ERROR_MESSAGES[InvalidPhoneError.Codes.INVALID_NUMBER],
                (
                    "0772345678",
                    "004477234567",
                    "00447723456",
                    "+44 (0)7723 456 78",
                ),
            ),
            (
                InvalidPhoneError.ERROR_MESSAGES[InvalidPhoneError.Codes.UNKNOWN_CHARACTER],
                (
                    "07890x32109",
                    "07723 456789...",
                    "07723 ☟☜⬇⬆☞☝",
                    "07723☟☜⬇⬆☞☝",
                    '07";DROP TABLE;"',
                    "+44 07ab cde fgh",
                    "ALPHANUM3R1C",
                ),
            ),
        ]
    ],
    [],
)

invalid_international_numbers = [
    ("80100000000", InvalidPhoneError.ERROR_MESSAGES[InvalidPhoneError.Codes.TOO_LONG]),
    ("1234567", InvalidPhoneError.ERROR_MESSAGES[InvalidPhoneError.Codes.INVALID_NUMBER]),
    (
        "+682 1234",
        InvalidPhoneError.ERROR_MESSAGES[InvalidPhoneError.Codes.INVALID_NUMBER],
    ),  # Cook Islands phone numbers can be 5 digits
    ("+12345 12345 12345 6", InvalidPhoneError.ERROR_MESSAGES[InvalidPhoneError.Codes.TOO_LONG]),
]


# NOTE: includes landlines
invalid_mobile_phone_numbers = (
    list(
        filter(
            lambda number: number[0]
            not in {
                "772345678910",  # Could be Russia
            },
            invalid_uk_mobile_phone_numbers,
        )
    )
    + invalid_international_numbers
    + [(num, InvalidPhoneError.ERROR_MESSAGES[InvalidPhoneError.Codes.INVALID_NUMBER]) for num in invalid_uk_landlines]
    + [(num, InvalidPhoneError.ERROR_MESSAGES[InvalidPhoneError.Codes.NOT_A_UK_MOBILE]) for num in valid_uk_landlines]
)
tv_numbers_phone_info_fixtures = [
    (
        "07700900010",
        international_phone_info(
            international=False,
            crown_dependency=False,
            country_prefix="44",
            rate_multiplier=1,
        ),
    ),
    (
        "447700900020",
        international_phone_info(
            international=False,
            crown_dependency=False,
            country_prefix="44",
            rate_multiplier=1,
        ),
    ),
    (
        "+447700900030",
        international_phone_info(
            international=False,
            crown_dependency=False,
            country_prefix="44",
            rate_multiplier=1,
        ),
    ),
]

international_phone_info_fixtures = [
    (
        "07723456789",
        international_phone_info(
            international=False,
            crown_dependency=False,
            country_prefix="44",  # UK
            rate_multiplier=1,
        ),
    ),
    (
        "07797800123",
        international_phone_info(
            international=True,
            crown_dependency=True,
            country_prefix="44",  # UK Crown dependency, so prefix same as UK
            rate_multiplier=1,
        ),
    ),
    (
        "20-12-1234-1234",
        international_phone_info(
            international=True,
            crown_dependency=False,
            country_prefix="20",  # Egypt
            rate_multiplier=3,
        ),
    ),
    (
        "00201212341234",
        international_phone_info(
            international=True,
            crown_dependency=False,
            country_prefix="20",  # Egypt
            rate_multiplier=3,
        ),
    ),
    (
        "16644913789",
        international_phone_info(
            international=True,
            crown_dependency=False,
            country_prefix="1664",  # Montserrat
            rate_multiplier=3,
        ),
    ),
    (
        "77234567890",
        international_phone_info(
            international=True,
            crown_dependency=False,
            country_prefix="7",  # Russia
            rate_multiplier=4,
        ),
    ),
    (
        "1-202-555-0104",
        international_phone_info(
            international=True,
            crown_dependency=False,
            country_prefix="1",  # USA
            rate_multiplier=1,
        ),
    ),
    (
        "+23052512345",
        international_phone_info(
            international=True,
            crown_dependency=False,
            country_prefix="230",  # Mauritius
            rate_multiplier=2,
        ),
    ),
]


@pytest.mark.parametrize("phone_number", valid_international_phone_numbers)
def test_detect_international_phone_numbers(phone_number):
    number = PhoneNumber(phone_number)
    assert not number.is_uk_phone_number()


@pytest.mark.parametrize("phone_number", valid_uk_mobile_phone_numbers)
def test_detect_uk_phone_numbers(phone_number):
    number = PhoneNumber(phone_number)
    assert number.is_uk_phone_number()


@pytest.mark.parametrize("phone_number, expected_info", international_phone_info_fixtures)
def test_get_international_info(phone_number, expected_info):
    number = PhoneNumber(phone_number)
    assert number.get_international_phone_info() == expected_info


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
def test_instantiating_phonenumber_raises_if_unparseable_characters(phone_number):
    with pytest.raises(InvalidPhoneError) as error:
        PhoneNumber(phone_number)
    assert str(error.value) == InvalidPhoneError.ERROR_MESSAGES[InvalidPhoneError.Codes.UNKNOWN_CHARACTER]


@pytest.mark.parametrize("phone_number", valid_uk_mobile_phone_numbers)
@pytest.mark.parametrize(
    "extra_args",
    [
        {},
        {"allow_international_number": False},
    ],
)
def test_phone_number_accepts_valid_values(extra_args, phone_number):
    try:
        number = PhoneNumber(phone_number)
        number.validate(**extra_args)
    except InvalidPhoneError:
        pytest.fail("Unexpected InvalidPhoneError")


@pytest.mark.parametrize("phone_number", valid_mobile_phone_numbers)
def test_phone_number_accepts_valid_international_values(phone_number):
    try:
        number = PhoneNumber(phone_number)
        number.validate(allow_international_number=True)
    except InvalidPhoneError:
        pytest.fail("Unexpected InvalidPhoneError")


@pytest.mark.parametrize("phone_number", valid_uk_mobile_phone_numbers)
def test_valid_uk_phone_number_can_be_formatted_consistently(phone_number):
    number = PhoneNumber(phone_number)
    assert number.get_normalised_format() == "447723456789"


@pytest.mark.parametrize(
    "phone_number, expected_formatted",
    [
        ("77234567890", "77234567890"),
        ("1-202-555-0104", "12025550104"),
        ("+12025550104", "12025550104"),
        ("0012025550104", "12025550104"),
        ("+0012025550104", "12025550104"),
        ("23052512345", "23052512345"),
    ],
)
def test_valid_international_phone_number_can_be_formatted_consistently(phone_number, expected_formatted):
    number = PhoneNumber(phone_number)
    assert number.get_normalised_format() == expected_formatted


@pytest.mark.parametrize("phone_number, error_message", invalid_uk_mobile_phone_numbers)
@pytest.mark.parametrize(
    "extra_args",
    [
        {},
        {"allow_international_number": False},
    ],
)
def test_phone_number_rejects_invalid_values(extra_args, phone_number, error_message):
    with pytest.raises(InvalidPhoneError) as e:
        number = PhoneNumber(phone_number)
        number.validate(**extra_args)
    assert error_message == str(e.value)


@pytest.mark.parametrize("phone_number, error_message", invalid_mobile_phone_numbers)
def test_phone_number_rejects_invalid_international_values(phone_number, error_message):
    with pytest.raises(InvalidPhoneError) as e:
        number = PhoneNumber(phone_number)
        number.validate(allow_international_number=True)
    assert error_message == str(e.value)


@pytest.mark.parametrize("phone_number", valid_uk_mobile_phone_numbers)
def test_validates_against_guestlist_of_phone_numbers(phone_number):
    assert allowed_to_send_to(phone_number, ["07723456789", "07700900460", "test@example.com"])
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
        ("16644918766", "+1 664-491-8766"),  # Montserrat
        ("7 499 1231212", "+7 499 123-12-12"),  # Moscow (Russia)
        ("1-202-555-0104", "+1 202-555-0104"),  # Washington DC (USA)
        ("+2304031001", "+230 403 1001"),  # Mauritius
        ("33(0)1 12345678", "+33 1 12 34 56 78"),  # Paris (France)
    ],
)
def test_format_uk_and_international_phone_numbers(phone_number, expected_formatted):
    number = PhoneNumber(phone_number)
    assert number.get_human_readable_format() == expected_formatted


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
        ("+1 928-282-4541", "19282824541"),
    ],
)
def test_format_recipient(recipient, expected_formatted):
    assert format_recipient(recipient) == expected_formatted


class TestPhoneNumberClass:
    @pytest.mark.parametrize("phone_number, error_message", invalid_uk_mobile_phone_numbers)
    def test_rejects_invalid_uk_mobile_phone_numbers(self, phone_number, error_message):
        # problem is `invalid_uk_mobile_phone_numbers` also includes valid uk landlines
        with pytest.raises(InvalidPhoneError):
            PhoneNumber(phone_number)
        # assert e.value.code == InvalidPhoneError.Codes.INVALID_NUMBER

    @pytest.mark.parametrize("phone_number", invalid_uk_landlines)
    def test_rejects_invalid_uk_landlines(self, phone_number):
        with pytest.raises(InvalidPhoneError) as e:
            PhoneNumber(phone_number)
        assert e.value.code == InvalidPhoneError.Codes.INVALID_NUMBER

    @pytest.mark.parametrize(
        "phone_number, error_message",
        invalid_uk_mobile_phone_numbers
        + invalid_international_numbers
        + [
            # french number - but 87 isn't a valid start of a phone number in france as defined by libphonenumber
            # eg https://github.com/google/libphonenumber/blob/master/resources/metadata/33/ranges.csv
            ("0033877123456", InvalidPhoneError.ERROR_MESSAGES[InvalidPhoneError.Codes.INVALID_NUMBER]),
        ],
    )
    def test_rejects_invalid_international_phone_numbers(self, phone_number, error_message):
        with pytest.raises(InvalidPhoneError):
            PhoneNumber(phone_number)

    @pytest.mark.parametrize("phone_number", valid_uk_mobile_phone_numbers)
    def test_allows_valid_uk_mobile_phone_numbers(self, phone_number):
        assert PhoneNumber(phone_number).is_uk_phone_number() is True

    @pytest.mark.parametrize("phone_number", valid_international_phone_numbers)
    def test_allows_valid_international_phone_numbers(self, phone_number):
        assert PhoneNumber(phone_number).is_uk_phone_number() is False

    @pytest.mark.parametrize("phone_number", valid_uk_landlines)
    def test_allows_valid_uk_landlines(self, phone_number):
        assert PhoneNumber(phone_number).is_uk_phone_number() is True

    @pytest.mark.parametrize("phone_number", valid_uk_landlines)
    def test_rejects_valid_uk_landlines_if_allow_landline_is_false(self, phone_number):
        with pytest.raises(InvalidPhoneError) as exc:
            number = PhoneNumber(phone_number)
            number.validate(allow_international_number=True, allow_uk_landline=False)
        assert exc.value.code == InvalidPhoneError.Codes.NOT_A_UK_MOBILE

    @pytest.mark.parametrize("phone_number, expected_info", international_phone_info_fixtures)
    def test_get_international_phone_info(self, phone_number, expected_info):
        assert PhoneNumber(phone_number).get_international_phone_info() == expected_info

    @pytest.mark.parametrize(
        "number, expected",
        [
            ("48123654789", False),  # Poland alpha: Yes
            ("1-403-555-0104", True),  # Canada alpha: No
            ("40 21 201 7200", False),  # Romania alpha: REG
            ("+60123451345", True),  # Malaysia alpha: NO
        ],
    )
    def test_should_use_numeric_sender(self, number, expected):
        assert PhoneNumber(number).should_use_numeric_sender() == expected

    @pytest.mark.parametrize("phone_number", valid_uk_mobile_phone_numbers)
    def test_get_normalised_format_works_for_uk_mobiles(self, phone_number):
        assert PhoneNumber(phone_number).get_normalised_format() == "447723456789"

    @pytest.mark.parametrize(
        "phone_number, expected_formatted",
        [
            ("74991231212", "74991231212"),
            ("1-202-555-0104", "12025550104"),
            ("+12025550104", "12025550104"),
            ("0012025550104", "12025550104"),
            ("+0012025550104", "12025550104"),
            ("23052512345", "23052512345"),
        ],
    )
    def test_get_normalised_format_works_for_international_numbers(self, phone_number, expected_formatted):
        assert str(PhoneNumber(phone_number)) == expected_formatted

    @pytest.mark.parametrize(
        "phone_number, expected_formatted",
        [
            ("07723456789", "07723 456789"),  # UK
            ("+44(0)7723456789", "07723 456789"),  # UK
            ("447723456789", "07723 456789"),  # UK
            ("20-12-1234-1234", "+20 12 12341234"),  # Egypt
            ("00201212341234", "+20 12 12341234"),  # Egypt
            ("1664 491 3789", "+1 664-491-3789"),  # Montserrat
            ("7 499 1231212", "+7 499 123-12-12"),  # Moscow (Russia)
            ("1-202-555-0104", "+1 202-555-0104"),  # Washington DC (USA)
            ("+23052512345", "+230 5251 2345"),  # Mauritius
            ("33(0)1 12345678", "+33 1 12 34 56 78"),  # Paris (France)
        ],
    )
    def test_get_human_readable_format(self, phone_number, expected_formatted):
        assert PhoneNumber(phone_number).get_human_readable_format() == expected_formatted

    # TODO: when we've removed the old style validation, we can just roll these in to our regular test fixtures
    # eg valid_uk_landline, invalid_uk_mobile_number, valid_international_number
    @pytest.mark.parametrize(
        "phone_number, expected_normalised_number",
        [
            # probably UK numbers
            ("+07044123456", "447044123456"),
            ("0+44(0)7779123456", "447779123456"),
            ("0+447988123456", "447988123456"),
            ("00447911123456", "447911123456"),
            ("04407379123456", "447379123456"),
            ("0447300123456", "447300123456"),
            ("000007392123456", "447392123456"),
            ("0007465123456", "447465123456"),
            ("007341123456", "447341123456"),
            # could be a UK landline, could be a US number. We assume UK landlines
            ("001708123456", "441708123456"),
            ("+01158123456", "441158123456"),
            ("+01323123456", "441323123456"),
            ("+03332123456", "443332123456"),
            # probably german
            ("+04915161123456", "4915161123456"),
        ],
    )
    def test_validate_normalised_succeeds(self, phone_number, expected_normalised_number):
        normalised_number = PhoneNumber(phone_number)
        assert str(normalised_number) == expected_normalised_number

    # TODO: decide if all these tests are useful to have.
    # they represent real (but obfuscated/anonymised) phone numbers that notify has sent to recently that
    # validated with the old code, but not with the new phonenumbers code
    @pytest.mark.parametrize(
        "phone_number, expected_error_code",
        [
            ("(07417)4123456", InvalidPhoneError.Codes.TOO_LONG),
            ("(06)25123456", InvalidPhoneError.Codes.INVALID_NUMBER),
            ("+00263 71123456", InvalidPhoneError.Codes.INVALID_NUMBER),
            ("+0065951123456", InvalidPhoneError.Codes.TOO_LONG),
            ("00129123456", InvalidPhoneError.Codes.INVALID_NUMBER),
            ("003570123456", InvalidPhoneError.Codes.INVALID_NUMBER),
            ("0038097123456", InvalidPhoneError.Codes.TOO_LONG),
            ("00407833123456", InvalidPhoneError.Codes.TOO_LONG),
            ("0041903123456", InvalidPhoneError.Codes.INVALID_NUMBER),
            ("005915209123456", InvalidPhoneError.Codes.TOO_LONG),
            ("00617584123456", InvalidPhoneError.Codes.INVALID_NUMBER),
            ("0064 495123456", InvalidPhoneError.Codes.INVALID_NUMBER),
            ("00667123456", InvalidPhoneError.Codes.INVALID_NUMBER),
            ("0092363123456", InvalidPhoneError.Codes.INVALID_NUMBER),
            ("009677337123456", InvalidPhoneError.Codes.TOO_LONG),
            ("047354123456", InvalidPhoneError.Codes.TOO_LONG),
            ("0049 160 123456", InvalidPhoneError.Codes.INVALID_NUMBER),
        ],
    )
    def test_validate_normalised_fails(self, phone_number, expected_error_code):
        with pytest.raises(InvalidPhoneError) as exc:
            PhoneNumber(phone_number)
        assert exc.value.code == expected_error_code

    @pytest.mark.parametrize(
        "phone_number, expected_valid_number",
        [("07700900010", "447700900010"), ("447700900020", "447700900020"), ("+447700900030", "447700900030")],
    )
    def test_tv_number_passes(self, phone_number, expected_valid_number):
        number = PhoneNumber(phone_number)
        assert expected_valid_number == str(number)

    @pytest.mark.parametrize("phone_number, expected_info", tv_numbers_phone_info_fixtures)
    def test_tv_number_returns_correct_international_info(self, phone_number, expected_info):
        number = PhoneNumber(phone_number)
        assert number.get_international_phone_info() == expected_info

    @pytest.mark.parametrize(
        "phone_number, expected_error_code",
        [
            ("+14158961600", InvalidPhoneError.Codes.NOT_A_UK_MOBILE),
            ("+3225484211", InvalidPhoneError.Codes.NOT_A_UK_MOBILE),
            ("+1 202-483-3000", InvalidPhoneError.Codes.NOT_A_UK_MOBILE),
            ("+7 495 308-78-41", InvalidPhoneError.Codes.NOT_A_UK_MOBILE),
            ("+74953087842", InvalidPhoneError.Codes.NOT_A_UK_MOBILE),
        ],
    )
    def test_international_does_not_normalise_to_uk_number(self, phone_number, expected_error_code):
        with pytest.raises(InvalidPhoneError) as exc:
            number = PhoneNumber(phone_number)
            number.validate(allow_international_number=False, allow_uk_landline=True)
        assert exc.value.code == expected_error_code

    @pytest.mark.parametrize(
        "phone_number", valid_uk_mobile_phone_numbers + valid_international_phone_numbers + valid_channel_island_numbers
    )
    def test_all_valid_numbers_parse_regardless_of_service_permissions(self, phone_number):
        """
        The PhoneNumber class should parse all numbers on instantiation regardless of permissions if they're
        a possible phone number. Checking whether a user or service can send that number should only be handled
        by the validate_phone_number method.
        """
        try:
            PhoneNumber(phone_number)
        except InvalidPhoneError:
            pytest.fail("Unexpected InvalidPhoneError")

    # We discovered a bug with the phone_numbers library causing some valid JE numbers
    # to evaluate as invalid. Realiably sending to Crown Dependencies is very important
    # this test serves to alert us if a known failing edge case arises again.
    @pytest.mark.parametrize("phone_number", valid_channel_island_numbers)
    def test_channel_island_numbers_are_valid(self, phone_number):
        try:
            number = PhoneNumber(phone_number)
            number.validate(allow_international_number=True, allow_uk_landline=False)
        except InvalidPhoneError:
            pytest.fail("Unexpected InvalidPhoneError")

    def test_validation_fails_for_unsupported_country_codes(self):
        number = PhoneNumber("24741111")

        with pytest.raises(InvalidPhoneError) as exc:
            number.validate(allow_international_number=True, allow_uk_landline=False)
        assert exc.value.code == InvalidPhoneError.Codes.UNSUPPORTED_COUNTRY_CODE


def test_empty_phone_number_is_rejected_with_correct_v2_error_message():
    phone_number = ""
    error_message = InvalidPhoneError(code=InvalidPhoneError.Codes.TOO_SHORT)
    with pytest.raises(InvalidPhoneError) as e:
        number = PhoneNumber(phone_number=phone_number)
        number.validate(allow_international_number=True, allow_uk_landline=False)
    assert str(error_message) == str(e.value)


@pytest.mark.parametrize("valid_three_digit_number", ["123", "888"])
def test_valid_three_digit_numbers_parse_if_is_service_contact_number_flag_set(valid_three_digit_number):
    number = PhoneNumber(valid_three_digit_number, is_service_contact_number=True)
    assert str(number.number.national_number) == valid_three_digit_number


@pytest.mark.parametrize("invalid_three_digit_number", ["999", "112"])
def test_invalid_three_digit_numbers_dont_parse_if_is_service_contact_number_flag_set(invalid_three_digit_number):
    error_message = InvalidPhoneError(code=InvalidPhoneError.Codes.UNSUPPORTED_EMERGENCY_NUMBER)
    with pytest.raises(InvalidPhoneError) as e:
        PhoneNumber(invalid_three_digit_number, is_service_contact_number=True)
    assert str(error_message) == str(e.value)
