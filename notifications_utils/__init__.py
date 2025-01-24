# Avoid further additions to this file as it will implicitly be imported before all utils
# imports and we need to be able to use parts of the utils package from an early stage of
# app bringup

import re

SMS_CHAR_COUNT_LIMIT = 918  # 153 * 6, no network issues but check with providers before upping this further
LETTER_MAX_PAGE_COUNT = 10

email_with_smart_quotes_regex = re.compile(
    # matches wider than an email - everything between an at sign and the nearest whitespace
    r"(^|\s)\S+@\S+(\s|$)",
    flags=re.MULTILINE,
)

# The magic sequence is a ‘unique’ series of characters which we temporarily insert
# and then later remove when performing tricky formatting operations
MAGIC_SEQUENCE = "🇬🇧🐦✉️"
magic_sequence_regex = re.compile(MAGIC_SEQUENCE)

ENGLISH_TO_WELSH_MONTHS = {
    "January": "Ionawr",
    "February": "Chwefror",
    "March": "Mawrth",
    "April": "Ebrill",
    "May": "Mai",
    "June": "Mehefin",
    "July": "Gorffennaf",
    "August": "Awst",
    "September": "Medi",
    "October": "Hydref",
    "November": "Tachwedd",
    "December": "Rhagfyr",
}
