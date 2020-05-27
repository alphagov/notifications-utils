import re

from notifications_utils.countries import UK, Country, CountryNotFoundError
from notifications_utils.countries.data import Postage
from notifications_utils.formatters import (
    normalise_lines,
    remove_whitespace_before_punctuation,
    remove_whitespace,
)


address_lines_1_to_6_keys = [
    # The API only accepts snake_case placeholders
    'address_line_1',
    'address_line_2',
    'address_line_3',
    'address_line_4',
    'address_line_5',
    'address_line_6',
]
address_lines_1_to_6_and_postcode_keys = address_lines_1_to_6_keys + ['postcode']
address_line_7_key = 'address_line_7'
address_lines_1_to_7_keys = address_lines_1_to_6_keys + [address_line_7_key]


class PostalAddress():

    MIN_LINES = 3
    MAX_LINES = 7

    def __init__(self, raw_address, allow_international_letters=False):
        self.raw_address = raw_address
        self.allow_international_letters = allow_international_letters

    def __bool__(self):
        return bool(self.normalised)

    def __repr__(self):
        return f'{self.__class__.__name__}({repr(self.raw_address)})'

    @classmethod
    def from_personalisation(cls, personalisation_dict, allow_international_letters=False):
        if address_line_7_key in personalisation_dict:
            keys = address_lines_1_to_6_keys + [address_line_7_key]
        else:
            keys = address_lines_1_to_6_and_postcode_keys
        return cls('\n'.join(
            str(personalisation_dict.get(key) or '') for key in keys
        ), allow_international_letters=allow_international_letters)

    @property
    def as_personalisation(self):
        lines = dict.fromkeys(address_lines_1_to_6_keys, '')
        lines.update({
            f'address_line_{index}': value
            for index, value in enumerate(self.normalised_lines[:-1], start=1)
            if index < 7
        })
        lines['postcode'] = lines['address_line_7'] = self.normalised_lines[-1]
        return lines

    @property
    def as_single_line(self):
        return ', '.join(self.normalised_lines)

    @property
    def country(self):
        try:
            return Country(self._lines[-1])
        except CountryNotFoundError:
            return Country(UK)

    @property
    def line_count(self):
        return len(self.normalised.splitlines())

    @property
    def has_enough_lines(self):
        return self.line_count >= self.MIN_LINES

    @property
    def has_too_many_lines(self):
        return self.line_count > self.MAX_LINES

    @property
    def has_valid_postcode(self):
        return self.postcode is not None

    @property
    def has_valid_last_line(self):
        return (
            self.allow_international_letters and self.international
        ) or self.has_valid_postcode

    @property
    def international(self):
        return self.postage != Postage.UK

    @property
    def _lines(self):
        return [
            remove_whitespace_before_punctuation(line.rstrip(' ,'))
            for line in normalise_lines(self.raw_address)
            if line.rstrip(' ,')
        ] or ['']

    @property
    def _lines_without_country(self):
        try:
            Country(self._lines[-1])
            return self._lines[:-1]
        except CountryNotFoundError:
            return self._lines

    @property
    def normalised(self):
        return '\n'.join(self.normalised_lines)

    @property
    def normalised_lines(self):

        if self.international:
            return self._lines_without_country + [self.country.canonical_name]

        if self.postcode:
            return self._lines_without_country[:-1] + [self.postcode]

        return self._lines_without_country

    @property
    def postage(self):
        return self.country.postage_zone

    @property
    def postcode(self):
        if self.international:
            return None
        last_line = self._lines_without_country[-1]
        if is_a_real_uk_postcode(last_line):
            return format_postcode_for_printing(last_line)

    @property
    def valid(self):
        return (
            self.has_valid_last_line
            and self.has_enough_lines
            and not self.has_too_many_lines
        )


def normalise_postcode(postcode):
    return remove_whitespace(postcode).upper()


def is_a_real_uk_postcode(postcode):
    standard = r"([A-Z]{1,2}[0-9][0-9A-Z]?[0-9][A-BD-HJLNP-UW-Z]{2})"
    bfpo = r"(BFPO?(C\/O)?[0-9]{1,4})"
    girobank = r"(GIR0AA)"
    pattern = r"{}|{}|{}".format(standard, bfpo, girobank)

    return bool(re.fullmatch(pattern, normalise_postcode(postcode)))


def format_postcode_for_printing(postcode):
    """
        This function formats the postcode so that it is ready for automatic sorting by Royal Mail.
        :param String postcode: A postcode that's already been validated by is_a_real_uk_postcode
    """
    postcode = normalise_postcode(postcode)
    if "BFPOC/O" in postcode:
        return postcode[:4] + " C/O " + postcode[7:]
    elif "BFPO" in postcode:
        return postcode[:4] + " " + postcode[4:]
    return postcode[:-3] + " " + postcode[-3:]
