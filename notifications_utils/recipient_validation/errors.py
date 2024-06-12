from enum import StrEnum, auto


class InvalidRecipientError(Exception):
    message = "Not a valid recipient address"

    def __init__(self, message: str = None):
        super().__init__(message or self.message)


class InvalidEmailError(InvalidRecipientError):
    message = "Not a valid email address"


class InvalidPhoneError(InvalidRecipientError):
    class Codes(StrEnum):
        INVALID_NUMBER = auto()
        TOO_LONG = auto()
        TOO_SHORT = auto()
        NOT_A_UK_MOBILE = auto()
        UNKNOWN_CHARACTER = auto()
        UNSUPPORTED_COUNTRY_CODE = auto()

    # TODO: Move this somewhere else maybe? Maybe not?
    ERROR_MESSAGES = {
        Codes.INVALID_NUMBER: "Not a valid phone number",
        Codes.TOO_LONG: "Mobile number is too long",
        Codes.TOO_SHORT: "Mobile number is too short",
        Codes.NOT_A_UK_MOBILE: (
            "This does not look like a UK mobile number – double check the mobile number you entered"
        ),
        Codes.UNKNOWN_CHARACTER: "Mobile numbers can only include: 0 1 2 3 4 5 6 7 8 9 ( ) + -",
        Codes.UNSUPPORTED_COUNTRY_CODE: "Country code not found - double check the mobile number you entered",
    }

    LEGACY_V2_API_ERROR_MESSAGES = ERROR_MESSAGES | {
        Codes.TOO_LONG: "Too many digits",
        Codes.TOO_SHORT: "Not enough digits",
        Codes.NOT_A_UK_MOBILE: "Not a UK mobile number",
        Codes.UNKNOWN_CHARACTER: "Must not contain letters or symbols",
        Codes.UNSUPPORTED_COUNTRY_CODE: "Not a valid country prefix",
    }

    def __init__(self, *, code: Codes = Codes.INVALID_NUMBER):
        """
        Create an InvalidPhoneError. The code must be present in InvalidPhoneError.ERROR_MESSAGES or this will raise a
        KeyError which you may not expect!
        """
        self.code = code
        super().__init__(message=self.ERROR_MESSAGES[code])

    def get_legacy_v2_api_error_message(self):
        return self.LEGACY_V2_API_ERROR_MESSAGES[self.code]


class InvalidAddressError(InvalidRecipientError):
    message = "Not a valid postal address"
