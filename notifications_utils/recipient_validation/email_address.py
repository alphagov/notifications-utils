import re

from notifications_utils.formatters import (
    strip_and_remove_obscure_whitespace,
)
from notifications_utils.recipient_validation.errors import InvalidEmailError

# Valid characters taken from https://en.wikipedia.org/wiki/Email_address#Local-part
# Note: Normal apostrophe eg `Firstname-o'surname@domain.com` is allowed.
# hostname_part regex: xn in regex signifies possible punycode conversions, which would start `xn--`;
# the hyphens are matched for later in the regex.
hostname_part = re.compile(r"^(xn|[a-z0-9]+)(-?-[a-z0-9]+)*$", re.IGNORECASE)
tld_part = re.compile(r"^([a-z]{2,63}|xn--([a-z0-9]+-)*[a-z0-9]+)$", re.IGNORECASE)
VALID_LOCAL_CHARS = r"a-zA-Z0-9.!#$%&'*+/=?^_`{|}~\-"
EMAIL_REGEX_PATTERN = rf"^[{VALID_LOCAL_CHARS}]+@([^.@][^@\s]+)$"


def validate_email_address(email_address):  # noqa (C901 too complex)
    # almost exactly the same as by https://github.com/wtforms/wtforms/blob/master/wtforms/validators.py,
    # with minor tweaks for SES compatibility - to avoid complications we are a lot stricter with the local part
    # than neccessary - we don't allow any double quotes or semicolons to prevent SES Technical Failures
    email_address = strip_and_remove_obscure_whitespace(email_address)
    match = re.match(EMAIL_REGEX_PATTERN, email_address)

    # not an email
    if not match:
        raise InvalidEmailError

    if len(email_address) > 320:
        raise InvalidEmailError

    # don't allow consecutive periods in either part
    if ".." in email_address:
        raise InvalidEmailError

    hostname = match.group(1)

    # idna = "Internationalized domain name" - this encode/decode cycle converts unicode into its accurate ascii
    # representation as the web uses. '例え.テスト'.encode('idna') == b'xn--r8jz45g.xn--zckzah'
    try:
        hostname = hostname.encode("idna").decode("ascii")
    except UnicodeError as e:
        raise InvalidEmailError from e

    parts = hostname.split(".")

    if len(hostname) > 253 or len(parts) < 2:
        raise InvalidEmailError

    for part in parts:
        if not part or len(part) > 63 or not hostname_part.match(part):
            raise InvalidEmailError

    # if the part after the last . is not a valid TLD then bail out
    if not tld_part.match(parts[-1]):
        raise InvalidEmailError

    return email_address


def format_email_address(email_address):
    return strip_and_remove_obscure_whitespace(email_address.lower())


def validate_and_format_email_address(email_address):
    return format_email_address(validate_email_address(email_address))
