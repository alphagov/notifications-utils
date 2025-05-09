import phonenumbers

from notifications_utils.international_billing_rates import (
    COUNTRY_PREFIXES,
)
from notifications_utils.recipient_validation.errors import InvalidPhoneError
from notifications_utils.recipient_validation.phone_number import LANDLINE_CODES
from notifications_utils.recipient_validation.phone_number import PhoneNumber as UkPhoneNumber

NL_PREFIX = "31"
NL_CODE = "NL"


class PhoneNumber(UkPhoneNumber):
    def __init__(self, phone_number: str, is_service_contact_number: bool = False):
        super().__init__(phone_number, is_service_contact_number)

    def _raise_if_service_cannot_send_to_international_but_tries_to(self, allow_international: bool = False):
        if not allow_international and str(self.number.country_code) != NL_PREFIX:
            raise InvalidPhoneError(code=InvalidPhoneError.Codes.NOT_A_DUTCH_MOBILE)

    def _raise_if_service_cannot_send_to_uk_landline_but_tries_to(self, allow_uk_landline: bool = False):
        if self.number.country_code != int(NL_PREFIX):
            return
        is_landline = phonenumbers.number_type(self.number) in LANDLINE_CODES
        if not allow_uk_landline and is_landline:
            raise InvalidPhoneError(code=InvalidPhoneError.Codes.NOT_A_DUTCH_MOBILE)

    def _raise_if_unsupported_country(self):
        if str(self.number.country_code) not in COUNTRY_PREFIXES | {f"+{NL_PREFIX}"}:
            raise InvalidPhoneError(code=InvalidPhoneError.Codes.UNSUPPORTED_COUNTRY_CODE)

    @staticmethod
    def _try_parse_number(phone_number):
        try:
            # parse number as NL - if there's no country code, try and parse it as a NL number
            return phonenumbers.parse(phone_number, NL_CODE)
        except phonenumbers.NumberParseException as e:
            raise InvalidPhoneError(code=InvalidPhoneError.Codes.INVALID_NUMBER) from e

    def is_uk_phone_number(self):
        return self.number.country_code == int(NL_PREFIX)

    def is_international_number(self):
        if phonenumbers.region_code_for_number(self.number) == NL_CODE:
            return False
        elif self._is_tv_number(self.number):
            return False
        else:
            return True

    def get_human_readable_format(self):
        # comparable to `format_phone_number_human_readable`
        return phonenumbers.format_number(
            self.number,
            (
                phonenumbers.PhoneNumberFormat.INTERNATIONAL
                if self.number.country_code != int(NL_PREFIX)
                else phonenumbers.PhoneNumberFormat.NATIONAL
            ),
        )
