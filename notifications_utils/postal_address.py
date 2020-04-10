from notifications_utils.countries import UK, Country, CountryNotFoundError
from notifications_utils.countries.data import Postage
from notifications_utils.formatters import (
    normalise_lines,
    remove_whitespace_before_punctuation,
)
from notifications_utils.recipients import (
    is_a_real_uk_postcode,
    first_column_headings,
    format_postcode_for_printing,
)


address_lines_1_to_6_and_postcode_keys = [
    # The API only accepts snake_case placeholders
    line.replace(' ', '_') for line in first_column_headings['letter']
]
address_lines_1_to_6_keys = address_lines_1_to_6_and_postcode_keys[:-1]
address_line_7_key = 'address_line_7'


class PostalAddress():

    MIN_LINES = 3
    MAX_LINES = 7

    def __init__(self, raw_address):
        self.raw_address = raw_address

    def __bool__(self):
        return bool(self.normalised)

    def __repr__(self):
        return f'{self.__class__.__name__}({repr(self.raw_address)})'

    @classmethod
    def from_personalisation(cls, personalisation_dict):
        if address_line_7_key in personalisation_dict:
            keys = address_lines_1_to_6_keys + [address_line_7_key]
        else:
            keys = address_lines_1_to_6_and_postcode_keys
        return cls('\n'.join(
            str(personalisation_dict.get(key) or '') for key in keys
        ))

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
    def international(self):
        return self.postage != Postage.UK

    @property
    def _lines(self):
        return [
            remove_whitespace_before_punctuation(line)
            for line in normalise_lines(self.raw_address) if line
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
        last_line = self._lines_without_country[-1]
        if is_a_real_uk_postcode(last_line):
            return format_postcode_for_printing(last_line)

    @property
    def valid(self):
        return (
            self.postcode
            and self.has_enough_lines
            and not self.has_too_many_lines
        )
