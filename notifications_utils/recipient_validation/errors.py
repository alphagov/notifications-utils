class InvalidRecipientError(Exception):
    message = "Not a valid recipient address"

    def __init__(self, message=None):
        super().__init__(message or self.message)


class InvalidEmailError(InvalidRecipientError):
    message = "Not a valid email address"


class InvalidPhoneError(InvalidRecipientError):
    message = "Not a valid phone number"


class InvalidAddressError(InvalidRecipientError):
    message = "Not a valid postal address"
