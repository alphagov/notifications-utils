import string
import re
import sys
import csv
import phonenumbers
from io import StringIO
from contextlib import suppress
from functools import lru_cache, partial
from itertools import islice
from collections import OrderedDict, namedtuple
from orderedset import OrderedSet

from flask import current_app

from . import EMAIL_REGEX_PATTERN, hostname_part, tld_part
from notifications_utils.formatters import (
    strip_and_remove_obscure_whitespace,
    strip_whitespace,
    OBSCURE_WHITESPACE
)
from notifications_utils.template import Template
from notifications_utils.columns import Columns, Row, Cell
from notifications_utils.international_billing_rates import (
    COUNTRY_PREFIXES,
    INTERNATIONAL_BILLING_RATES,
)
from notifications_utils.postal_address import (
    address_line_7_key,
    address_lines_1_to_6_and_postcode_keys,
    address_lines_1_to_7_keys,
)


uk_prefix = '44'

first_column_headings = {
    'email': ['email address'],
    'sms': ['phone number'],
    'letter': [
        line.replace('_', ' ')
        for line in address_lines_1_to_6_and_postcode_keys + [address_line_7_key]
    ],
}

address_columns = Columns.from_keys(first_column_headings['letter'])


class RecipientCSV():

    max_rows = 50000

    def __init__(
        self,
        file_data,
        template,
        max_errors_shown=20,
        max_initial_rows_shown=10,
        whitelist=None,
        remaining_messages=sys.maxsize,
        allow_international_sms=False,
        allow_international_letters=False,
    ):
        self.file_data = strip_whitespace(file_data, extra_characters=',')
        self.max_errors_shown = max_errors_shown
        self.max_initial_rows_shown = max_initial_rows_shown
        self.whitelist = whitelist
        self.template = template
        self.allow_international_sms = allow_international_sms
        self.allow_international_letters = allow_international_letters
        self.remaining_messages = remaining_messages
        self.rows_as_list = None

    def __len__(self):
        if not hasattr(self, '_len'):
            self._len = len(self.rows)
        return self._len

    def __getitem__(self, requested_index):
        return self.rows[requested_index]

    @property
    def whitelist(self):
        return self._whitelist

    @whitelist.setter
    def whitelist(self, value):
        try:
            self._whitelist = list(value)
        except TypeError:
            self._whitelist = []

    @property
    def template(self):
        return self._template

    @template.setter
    def template(self, value):
        if not isinstance(value, Template):
            raise TypeError(
                'template must be an instance of '
                'notifications_utils.template.Template'
            )
        self._template = value
        self.template_type = self._template.template_type
        self.recipient_column_headers = first_column_headings[self.template_type]
        self.placeholders = self._template.placeholders

    @property
    def placeholders(self):
        return self._placeholders

    @placeholders.setter
    def placeholders(self, value):
        try:
            self._placeholders = list(value) + self.recipient_column_headers
        except TypeError:
            self._placeholders = self.recipient_column_headers
        self.placeholders_as_column_keys = [
            Columns.make_key(placeholder)
            for placeholder in self._placeholders
        ]
        self.recipient_column_headers_as_column_keys = [
            Columns.make_key(placeholder)
            for placeholder in self.recipient_column_headers
        ]

    @property
    def has_errors(self):
        return bool(
            self.missing_column_headers or
            self.duplicate_recipient_column_headers or
            self.more_rows_than_can_send or
            self.too_many_rows or
            (not self.allowed_to_send_to) or
            any(self.rows_with_errors)
        )  # `or` is 3x faster than using `any()` here

    @property
    def allowed_to_send_to(self):
        if self.template_type == 'letter':
            return True
        if not self.whitelist:
            return True
        return all(
            allowed_to_send_to(row.recipient, self.whitelist)
            for row in self.rows
        )

    @property
    def rows(self):
        if self.rows_as_list is None:
            self.rows_as_list = list(self.get_rows())
        return self.rows_as_list

    @property
    def _rows(self):
        return csv.reader(
            StringIO(self.file_data.strip()),
            quoting=csv.QUOTE_MINIMAL,
            skipinitialspace=True,
        )

    def get_rows(self):

        column_headers = self._raw_column_headers  # this is for caching
        length_of_column_headers = len(column_headers)

        rows_as_lists_of_columns = self._rows

        next(rows_as_lists_of_columns, None)  # skip the header row

        for index, row in enumerate(rows_as_lists_of_columns):

            output_dict = OrderedDict()

            for column_name, column_value in zip(column_headers, row):

                column_value = strip_and_remove_obscure_whitespace(column_value)

                if Columns.make_key(column_name) in self.recipient_column_headers_as_column_keys:
                    output_dict[column_name] = column_value or None
                else:
                    insert_or_append_to_dict(output_dict, column_name, column_value or None)

            length_of_row = len(row)

            if length_of_column_headers < length_of_row:
                output_dict[None] = row[length_of_column_headers:]
            elif length_of_column_headers > length_of_row:
                for key in column_headers[length_of_row:]:
                    insert_or_append_to_dict(output_dict, key, None)

            if index < self.max_rows:
                yield Row(
                    output_dict,
                    index=index,
                    error_fn=self._get_error_for_field,
                    recipient_column_headers=self.recipient_column_headers,
                    placeholders=self.placeholders_as_column_keys,
                    template=self.template,
                    allow_international_letters=self.allow_international_letters,
                )
            else:
                yield None

    @property
    def more_rows_than_can_send(self):
        return len(self) > self.remaining_messages

    @property
    def too_many_rows(self):
        return len(self) > self.max_rows

    @property
    def initial_rows(self):
        return islice(self.rows, self.max_initial_rows_shown)

    @property
    def displayed_rows(self):
        if any(self.rows_with_errors) and not self.missing_column_headers:
            return self.initial_rows_with_errors
        return self.initial_rows

    def _filter_rows(self, attr):
        return (row for row in self.rows if row and getattr(row, attr))

    @property
    def rows_with_errors(self):
        return self._filter_rows('has_error')

    @property
    def rows_with_bad_recipients(self):
        return self._filter_rows('has_bad_recipient')

    @property
    def rows_with_missing_data(self):
        return self._filter_rows('has_missing_data')

    @property
    def rows_with_message_too_long(self):
        return self._filter_rows('message_too_long')

    @property
    def rows_with_empty_message(self):
        return self._filter_rows('message_empty')

    @property
    def initial_rows_with_errors(self):
        return islice(self.rows_with_errors, self.max_errors_shown)

    @property
    def _raw_column_headers(self):
        for row in self._rows:
            return row
        return []

    @property
    def column_headers(self):
        return list(OrderedSet(self._raw_column_headers))

    @property
    def column_headers_as_column_keys(self):
        return Columns.from_keys(self.column_headers).keys()

    @property
    def missing_column_headers(self):
        return set(
            key for key in self.placeholders
            if (
                Columns.make_key(key) not in self.column_headers_as_column_keys and
                not self.is_address_column(key)
            )
        )

    @property
    def duplicate_recipient_column_headers(self):

        raw_recipient_column_headers = [
            Columns.make_key(column_header)
            for column_header in self._raw_column_headers
            if Columns.make_key(column_header) in self.recipient_column_headers_as_column_keys
        ]

        return OrderedSet((
            column_header
            for column_header in self._raw_column_headers
            if raw_recipient_column_headers.count(Columns.make_key(column_header)) > 1
        ))

    def is_address_column(self, key):
        return (
            self.template_type == 'letter' and key in address_columns
        )

    @property
    def count_of_required_recipient_columns(self):
        return 3 if self.template_type == 'letter' else 1

    @property
    def has_recipient_columns(self):

        if self.template_type == 'letter':
            sets_to_check = [
                Columns.from_keys(address_lines_1_to_6_and_postcode_keys).keys(),
                Columns.from_keys(address_lines_1_to_7_keys).keys(),
            ]
        else:
            sets_to_check = [
                self.recipient_column_headers_as_column_keys,
            ]

        for set_to_check in sets_to_check:
            if len(
                # Work out which columns are shared between the possible
                # letter address columns and the columns in the user’s
                # spreadsheet (`&` means set intersection)
                set_to_check & self.column_headers_as_column_keys
            ) >= self.count_of_required_recipient_columns:
                return True

        return False

    def _get_error_for_field(self, key, value):  # noqa: C901

        if self.is_address_column(key):
            return

        if Columns.make_key(key) in self.recipient_column_headers_as_column_keys:
            if value in [None, ''] or isinstance(value, list):
                if self.duplicate_recipient_column_headers:
                    return None
                else:
                    return Cell.missing_field_error
            try:
                validate_recipient(
                    value,
                    self.template_type,
                    allow_international_sms=self.allow_international_sms
                )
            except (InvalidEmailError, InvalidPhoneError) as error:
                return str(error)

        if Columns.make_key(key) not in self.placeholders_as_column_keys:
            return

        if value in [None, '']:
            return Cell.missing_field_error


class InvalidEmailError(Exception):

    def __init__(self, message=None):
        super().__init__(message or 'Not a valid email address')


class InvalidPhoneError(InvalidEmailError):
    pass


class InvalidAddressError(InvalidEmailError):
    pass


def normalise_phone_number(number):

    for character in string.whitespace + OBSCURE_WHITESPACE + '()-+':
        number = number.replace(character, '')

    try:
        list(map(int, number))
    except ValueError:
        raise InvalidPhoneError('Must not contain letters or symbols')

    return number.lstrip('0')


def is_uk_phone_number(number):

    if (
        (number.startswith('0') and not number.startswith('00'))
    ):
        return True

    number = normalise_phone_number(number)

    if (
        number.startswith(uk_prefix) or
        (number.startswith('7') and len(number) < 11)
    ):
        return True

    return False


international_phone_info = namedtuple('PhoneNumber', [
    'international',
    'country_prefix',
    'billable_units',
])


def get_international_phone_info(number):

    number = validate_phone_number(number, international=True)
    prefix = get_international_prefix(number)

    return international_phone_info(
        international=(prefix != uk_prefix or _is_a_crown_dependency_number(number)),
        country_prefix=prefix,
        billable_units=get_billable_units_for_prefix(prefix)
    )


CROWN_DEPENDENCY_RANGES = ['7781', '7839', '7911', '7509', '7797', '7937', '7700', '7829', '7624', '7524', '7924']


def _is_a_crown_dependency_number(number):
    return number[2:6] in CROWN_DEPENDENCY_RANGES


def get_international_prefix(number):
    return next(
        (prefix for prefix in COUNTRY_PREFIXES if number.startswith(prefix)),
        None
    )


def get_billable_units_for_prefix(prefix):
    return INTERNATIONAL_BILLING_RATES[prefix]['billable_units']


def validate_uk_phone_number(number, column=None):

    number = normalise_phone_number(number).lstrip(uk_prefix).lstrip('0')

    if not number.startswith('7'):
        raise InvalidPhoneError('Not a UK mobile number')

    if len(number) > 10:
        raise InvalidPhoneError('Too many digits')

    if len(number) < 10:
        raise InvalidPhoneError('Not enough digits')

    return '{}{}'.format(uk_prefix, number)


def validate_phone_number(number, column=None, international=False):

    if (not international) or is_uk_phone_number(number):
        return validate_uk_phone_number(number)

    number = normalise_phone_number(number)

    if len(number) < 8:
        raise InvalidPhoneError('Not enough digits')

    if get_international_prefix(number) is None:
        raise InvalidPhoneError('Not a valid country prefix')

    return number


validate_and_format_phone_number = validate_phone_number


def try_validate_and_format_phone_number(number, column=None, international=None, log_msg=None):
    """
    For use in places where you shouldn't error if the phone number is invalid - for example if firetext pass us
    something in
    """
    try:
        return validate_and_format_phone_number(number, column, international)
    except InvalidPhoneError as exc:
        if log_msg:
            current_app.logger.warning('{}: {}'.format(log_msg, exc))
        return number


def validate_email_address(email_address, column=None):  # noqa (C901 too complex)
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
    if '..' in email_address:
        raise InvalidEmailError

    hostname = match.group(1)

    # idna = "Internationalized domain name" - this encode/decode cycle converts unicode into its accurate ascii
    # representation as the web uses. '例え.テスト'.encode('idna') == b'xn--r8jz45g.xn--zckzah'
    try:
        hostname = hostname.encode('idna').decode('ascii')
    except UnicodeError:
        raise InvalidEmailError

    parts = hostname.split('.')

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


def validate_recipient(recipient, template_type, allow_international_sms=False):
    return {
        'email': validate_email_address,
        'sms': partial(validate_phone_number, international=allow_international_sms),
    }[template_type](recipient)


@lru_cache(maxsize=32, typed=False)
def format_recipient(recipient):
    if not isinstance(recipient, str):
        return ''
    with suppress(InvalidPhoneError):
        return validate_and_format_phone_number(recipient)
    with suppress(InvalidEmailError):
        return validate_and_format_email_address(recipient)
    return recipient


def format_phone_number_human_readable(phone_number):
    try:
        phone_number = validate_phone_number(phone_number, international=True)
    except InvalidPhoneError:
        # if there was a validation error, we want to shortcut out here, but still display the number on the front end
        return phone_number
    international_phone_info = get_international_phone_info(phone_number)

    return phonenumbers.format_number(
        phonenumbers.parse('+' + phone_number, None),
        (
            phonenumbers.PhoneNumberFormat.INTERNATIONAL
            if international_phone_info.international
            else phonenumbers.PhoneNumberFormat.NATIONAL
        )
    )


def allowed_to_send_to(recipient, whitelist):
    return format_recipient(recipient) in [
        format_recipient(recipient) for recipient in whitelist
    ]


def insert_or_append_to_dict(dict_, key, value):
    if dict_.get(key):
        if isinstance(dict_[key], list):
            dict_[key].append(value)
        else:
            dict_[key] = [dict_[key], value]
    else:
        dict_.update({key: value})
