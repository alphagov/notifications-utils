from enum import StrEnum, auto

import phonenumbers


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
        NOT_A_DUTCH_MOBILE = auto()
        UNKNOWN_CHARACTER = auto()
        UNSUPPORTED_COUNTRY_CODE = auto()
        UNSUPPORTED_EMERGENCY_NUMBER = auto()

    # TODO: Move this somewhere else maybe? Maybe not?
    ERROR_MESSAGES = {
        # this catches numbers with the right length but wrong digits
        # for example UK numbers cannot start "06" as that hasn't been assigned to a purpose by ofcom,
        # or a 9 digit UK number that does not start "01" or "0800".
        Codes.INVALID_NUMBER: "Het telefoonnummer is ongeldig – controleer het telefoonnummer dat je hebt ingevoerd",
        Codes.TOO_LONG: "Het mobiele telefoonnummer is te lang",
        Codes.TOO_SHORT: "Het mobiele telefoonnummer is te kort",
        Codes.NOT_A_UK_MOBILE: (
            "Dit lijkt geen Brits mobiel telefoonnummer te zijn – controleer het \
            mobiele nummtelefoonnummerr dat je hebt ingevoerd"
        ),
        Codes.NOT_A_DUTCH_MOBILE: (
            "Dit lijkt geen Nederlands mobiel telefoonnummer te zijn – controleer \
            het mobiele telefoonnummer dat je hebt ingevoerd"
        ),
        Codes.UNKNOWN_CHARACTER: (
            "Mobiele nummers mogen alleen de volgende tekens bevatten: 0 1 2 3 4 5 6 7 8 9 ( ) + -"
        ),
        Codes.UNSUPPORTED_COUNTRY_CODE: (
            "Landcode niet gevonden – controleer het mobiele telefoonnummer dat je hebt ingevoerd"
        ),
        Codes.UNSUPPORTED_EMERGENCY_NUMBER: ("Het telefoonnummer mag geen alarmnummer zijn"),
    }

    LEGACY_V2_API_ERROR_MESSAGES = ERROR_MESSAGES | {
        Codes.TOO_LONG: "Too many digits",
        Codes.TOO_SHORT: "Not enough digits",
        Codes.NOT_A_UK_MOBILE: "Not a UK mobile number",
        Codes.NOT_A_DUTCH_MOBILE: "Not a dutch mobile number",
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

    @classmethod
    def from_phonenumbers_validation_result(cls, reason: phonenumbers.ValidationResult) -> str:
        match reason:
            case phonenumbers.ValidationResult.TOO_LONG:
                code = cls.Codes.TOO_LONG
            # is_possible_local_only implies a number without an area code. Lets just call it too short.
            case phonenumbers.ValidationResult.TOO_SHORT | phonenumbers.ValidationResult.IS_POSSIBLE_LOCAL_ONLY:
                code = cls.Codes.TOO_SHORT
            case phonenumbers.ValidationResult.INVALID_COUNTRY_CODE:
                code = cls.Codes.UNSUPPORTED_COUNTRY_CODE
            case phonenumbers.ValidationResult.IS_POSSIBLE:
                raise ValueError("Cannot create InvalidPhoneNumber for ValidationResult.IS_POSSIBLE")
            case phonenumbers.ValidationResult.INVALID_LENGTH:
                code = cls.Codes.INVALID_NUMBER

            case _:
                code = cls.Codes.INVALID_NUMBER

        return cls(code=code)

    def get_legacy_v2_api_error_message(self):
        return self.LEGACY_V2_API_ERROR_MESSAGES[self.code]


class InvalidAddressError(InvalidRecipientError):
    message = "Not a valid postal address"
