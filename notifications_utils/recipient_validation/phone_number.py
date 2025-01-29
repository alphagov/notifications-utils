import re
from collections import namedtuple
from contextlib import suppress

import phonenumbers

from notifications_utils.formatters import (
    ALL_WHITESPACE,
)
from notifications_utils.international_billing_rates import (
    COUNTRY_PREFIXES,
    INTERNATIONAL_BILLING_RATES,
)
from notifications_utils.recipient_validation.errors import InvalidPhoneError

UK_PREFIX = "44"

EMERGENCY_THREE_DIGIT_NUMBERS = [
    "999",
    "112",
]

LANDLINE_CODES = {
    phonenumbers.PhoneNumberType.FIXED_LINE,
    phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE,
    phonenumbers.PhoneNumberType.UAN,
}

ALLOW_LIST = {
    phonenumbers.PhoneNumberType.FIXED_LINE,
    phonenumbers.PhoneNumberType.MOBILE,
    phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE,  # ambiguous case where a number could be either landline/mobile
    phonenumbers.PhoneNumberType.UAN,
    phonenumbers.PhoneNumberType.PERSONAL_NUMBER,
}

DENY_LIST = [
    phonenumbers.PhoneNumberType.PREMIUM_RATE,
]

international_phone_info = namedtuple(
    "PhoneNumber",
    [
        "international",
        "crown_dependency",
        "country_prefix",
        "rate_multiplier",
    ],
)

CROWN_DEPENDENCY_RANGES = ["7781", "7839", "7911", "7509", "7797", "7937", "7700", "7829", "7624", "7524", "7924"]


class PhoneNumber:
    """
    A class that parses and performs validation checks on phonenumbers against service permissions

    Can be instantiated for all Phone Numbers other than premium numbers. Instansiation checks that the number
    you are trying to send to is possible, validate checks the number against a services permissions passed to it
    to ensure it can send.

    Examples:
        number = PhoneNumber("07910777555")
        number.validate(allow_international_number = False, allow_uk_landline = False)
    """

    def __init__(self, phone_number: str, is_service_contact_number: bool = False) -> None:
        self.is_service_contact_number = is_service_contact_number
        try:
            self.number = self.parse_phone_number(phone_number)
        except InvalidPhoneError:
            phone_number = self._thoroughly_normalise_number(phone_number)
            self.number = self.parse_phone_number(phone_number)
        self._phone_number = phone_number

    def _raise_if_service_cannot_send_to_international_but_tries_to(self, allow_international: bool = False):
        if not allow_international and str(self.number.country_code) != UK_PREFIX:
            raise InvalidPhoneError(code=InvalidPhoneError.Codes.NOT_A_UK_MOBILE)

    def _raise_if_service_cannot_send_to_uk_landline_but_tries_to(self, allow_uk_landline: bool = False):
        if self.number.country_code != int(UK_PREFIX):
            return
        is_landline = phonenumbers.number_type(self.number) in LANDLINE_CODES
        if not allow_uk_landline and is_landline:
            raise InvalidPhoneError(code=InvalidPhoneError.Codes.NOT_A_UK_MOBILE)

    def _raise_if_unsupported_country(self):
        if str(self.number.country_code) not in COUNTRY_PREFIXES | {"+44"}:
            raise InvalidPhoneError(code=InvalidPhoneError.Codes.UNSUPPORTED_COUNTRY_CODE)

    def validate(self, allow_international_number: bool = False, allow_uk_landline: bool = False) -> None:
        self._raise_if_service_cannot_send_to_international_but_tries_to(allow_international=allow_international_number)
        self._raise_if_service_cannot_send_to_uk_landline_but_tries_to(allow_uk_landline=allow_uk_landline)
        self._raise_if_unsupported_country()

    @staticmethod
    def _try_parse_number(phone_number):
        try:
            # parse number as GB - if there's no country code, try and parse it as a UK number
            return phonenumbers.parse(phone_number, "GB")
        except phonenumbers.NumberParseException as e:
            raise InvalidPhoneError(code=InvalidPhoneError.Codes.INVALID_NUMBER) from e

    @staticmethod
    def _raise_if_phone_number_is_empty(number: str) -> None:
        if number == "" or number is None:
            raise InvalidPhoneError(code=InvalidPhoneError.Codes.TOO_SHORT)

    @staticmethod
    def _raise_if_phone_number_contains_invalid_characters(number: str) -> None:
        chars = set(number)
        if chars - {*ALL_WHITESPACE + "()-+" + "0123456789"}:
            raise InvalidPhoneError(code=InvalidPhoneError.Codes.UNKNOWN_CHARACTER)

    def parse_phone_number(self, phone_number: str) -> phonenumbers.PhoneNumber:
        """
        Parse a phone number and return the PhoneNumber object

        Tries best effort parsing of a number (without any consideration for a services permissions), and has some extra
        logic to make the validation closer to our existing validation
        including:

        * Being stricter with rogue alphanumeric characters. (eg don't allow https://en.wikipedia.org/wiki/Phoneword)
        * Additional parsing steps to check if there was a + or leading 0 stripped off the beginning of the number that
          changes whether it is parsed as international or not.
        * Convert error codes to match existing Notify error codes
        """
        # notify's old validation code is stricter than phonenumbers in not allowing letters etc, so need to catch some
        # of those cases separately before we parse with the phonenumbers library
        self._raise_if_phone_number_contains_invalid_characters(phone_number)
        self._raise_if_phone_number_is_empty(phone_number)

        number = self._try_parse_number(phone_number)
        if self.is_service_contact_number and len(str(number.national_number)) == 3:
            if str(number.national_number) in EMERGENCY_THREE_DIGIT_NUMBERS:
                raise InvalidPhoneError(code=InvalidPhoneError.Codes.UNSUPPORTED_EMERGENCY_NUMBER)
            return number

        if (reason := phonenumbers.is_possible_number_with_reason(number)) != phonenumbers.ValidationResult.IS_POSSIBLE:
            if forced_international_number := self._validate_forced_international_number(phone_number):
                number = forced_international_number
            else:
                raise InvalidPhoneError.from_phonenumbers_validation_result(reason)
        if not (phonenumbers.is_valid_number(number) & self._is_allowed_phone_number_type(number)):
            # is_possible just checks the length of a number for that country/region. is_valid checks if it's
            # a valid sequence of numbers. This doesn't cover "is this number registered to an MNO".
            # For example UK numbers cannot start "06" as that hasn't been assigned to a purpose by ofcom
            if self._is_tv_number(number):
                return number
            else:
                raise InvalidPhoneError(code=InvalidPhoneError.Codes.INVALID_NUMBER)

        return number

    @staticmethod
    def _is_allowed_phone_number_type(phone_number: phonenumbers.PhoneNumber) -> bool:
        if phonenumbers.number_type(phone_number) in DENY_LIST:
            return False
        if phonenumbers.number_type(phone_number) in ALLOW_LIST:
            return True
        return False

    @staticmethod
    def _is_tv_number(phone_number) -> bool:
        """
        The phonenumbers library does not consider TV numbers (fake numbers OFCOM reserves use in TV, film etc)
        valid. This method checks whether a normalised phone number that has failed the library's validation is
        in fact a valid TV number
        """
        phone_number_as_string = str(phone_number.national_number)
        if re.match("7700[900000-900999]", phone_number_as_string):
            return True

    @staticmethod
    def _thoroughly_normalise_number(phone_number: str) -> str:
        """
        We often (up to ~3% of the time) see numbers which are not technically valid, but are close-enough-to-valid
        that we want to give our users benefit of the doubt.

        We don't want to do this for every number, because if someone passes in a valid international number that
        like "+1 (500) 555-1234" then we don't want to remove the + sign as we may then confuse it with a UK landline

        This includes numbers like:

        "0+447700900100" (a stray leading 0)
        "000007700900100" (five leading zeros)
        "+07700900100" (a leading plus but no country code)
        "0+44(0)7700900100" (a mix of all of the above)
        """
        return phone_number.replace("+", "").lstrip("0")

    @staticmethod
    def _validate_forced_international_number(phone_number: str) -> phonenumbers.PhoneNumber | None:
        """
        phonenumbers assumes a number without a + or 00 at beginning is always a local number. Given that we know excel
        sometimes strips these, if it doesn't parse as a UK number, lets try forcing it to be recognised as an
        international number
        """
        with suppress(phonenumbers.NumberParseException):
            forced_international_number = phonenumbers.parse(f"+{phone_number}")

            if phonenumbers.is_possible_number(forced_international_number):
                return forced_international_number

        return None

    @property
    def prefix(self):
        """
        Returns the international dialing code for looking up data in our international_billing_rates.yml file

        in our billing rates yml file, countries in the North American Numbering Plan (+1) may fall under
        US/Canada/Dominican Republic (just +1) or they may have their own specific area code within the plan, eg
        Montserrat with numbers like "+1 664 xxx xxxx". This means we need to check the area code first to see if
        it's a regular area code or a full country code.
        """
        if self.number.country_code == 1:
            country_and_area_code = phonenumbers.format_number(self.number, phonenumbers.PhoneNumberFormat.E164)[1:5]
            if country_and_area_code in INTERNATIONAL_BILLING_RATES:
                return country_and_area_code
        return str(self.number.country_code)

    def is_uk_phone_number(self):
        """
        Returns if the number starts with +44. Note, this includes international numbers for crown dependencies such as
        jersey/guernsey.

        # TODO: check if we still need this - looking at api, this might be able to be removed entirely since it's
        # always used in conjunction with should_use_numeric_sender
        """
        return self.number.country_code == 44

    def get_international_phone_info(self):
        return international_phone_info(
            international=self.is_international_number(),
            crown_dependency=self.is_a_crown_dependency_number(),
            country_prefix=self.prefix,
            rate_multiplier=INTERNATIONAL_BILLING_RATES[self.prefix]["rate_multiplier"],
        )

    def is_international_number(self):
        """
        Returns True for phone numbers that either have a GB country code
        or that are OFCOM TV numbers. libphonenumber only contains actually
        valid phonenumbers in its metadata, so TV numbers will return null
        values calling methods like `phonenumbers.region_code_fornumber` so
        need handling as a special case.
        """
        if phonenumbers.region_code_for_number(self.number) == "GB":
            return False
        elif self._is_tv_number(self.number):
            return False
        else:
            return True

    def is_a_crown_dependency_number(self):
        """
        Returns True for phone numbers from Jersey, Guernsey, Isle of Man, etc
        TV numbers are an edge case where libphonenumber cannot accurately
        handle them (they're not actually valid numbers). In that case we
        always want to return False as we consider them to be UK numbers.
        """
        if self._is_tv_number(self.number):
            return False
        else:
            return self.is_uk_phone_number() and phonenumbers.region_code_for_number(self.number) != "GB"

    def should_use_numeric_sender(self):
        """
        Some countries need a specific sender to be used rather than whatever the service has specified
        """
        return INTERNATIONAL_BILLING_RATES[self.prefix]["attributes"]["alpha"] == "NO"

    def get_normalised_format(self):
        return str(self)

    def __str__(self):
        """
        Returns a normalised phone number including international country code suitable to send to providers
        """
        formatted = phonenumbers.format_number(self.number, phonenumbers.PhoneNumberFormat.E164)
        # strip the plus and just pass numbers to our suppliers.
        # TODO: If our suppliers let us send the plus, then we should do so, for consistency/accuracy.
        return formatted[1:]

    def get_human_readable_format(self):
        # comparable to `format_phone_number_human_readable`
        return phonenumbers.format_number(
            self.number,
            (
                phonenumbers.PhoneNumberFormat.INTERNATIONAL
                if self.number.country_code != 44
                else phonenumbers.PhoneNumberFormat.NATIONAL
            ),
        )
