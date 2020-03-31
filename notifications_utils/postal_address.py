from notifications_utils.countries import UK, Country, CountryNotFoundError
from notifications_utils.countries.data import Postage
from notifications_utils.formatters import (
    normalise_lines,
    remove_whitespace_before_punctuation,
)
from notifications_utils.recipients import (
    is_a_real_uk_postcode,
    format_postcode_for_printing,
)


class PostalAddress():

    MIN_LINES = 3
    MAX_LINES = 7

    def __init__(self, raw_address):
        self.raw_address = raw_address

    @property
    def country(self):
        try:
            return Country(self._lines[-1])
        except CountryNotFoundError:
            return Country(UK)

    @property
    def count_of_lines(self):
        return len(self.normalised.splitlines())

    @property
    def has_enough_lines(self):
        return self.count_of_lines >= self.MIN_LINES

    @property
    def has_too_many_lines(self):
        return self.count_of_lines > self.MAX_LINES

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
