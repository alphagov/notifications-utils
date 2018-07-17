import re

SMS_CHAR_COUNT_LIMIT = 459  # 153 * 3

# regexes for use in recipients.validate_email_address.
# Valid characters taken from https://en.wikipedia.org/wiki/Email_address#Local-part
# Note: Normal apostrophe eg `Firstname-o'surname@domain.com` is allowed.
hostname_part = re.compile(r'^(xn-|[a-z0-9]+)(-[a-z0-9]+)*$', re.IGNORECASE)
tld_part = re.compile(r'^([a-z]{2,63}|xn--([a-z0-9]+-)*[a-z0-9]+)$', re.IGNORECASE)
VALID_LOCAL_CHARS = r"a-zA-Z0-9.!#$%&'*+/=?^_`{|}~\-"
EMAIL_REGEX_PATTERN = r'^[{}]+@([^.@][^@\s]+)$'
email_regex = re.compile(EMAIL_REGEX_PATTERN.format(VALID_LOCAL_CHARS))
email_with_smart_quotes_regex = re.compile(
    EMAIL_REGEX_PATTERN[1:-1].format(VALID_LOCAL_CHARS + '‘’'),
    flags=re.MULTILINE,
)
