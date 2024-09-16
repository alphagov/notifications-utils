import re
from functools import lru_cache

from notifications_utils.countries import UK, Country, CountryNotFoundError
from notifications_utils.countries.data import UK_POSTCODE_ZONES, Postage
from notifications_utils.formatters import (
    get_lines_with_normalised_whitespace,
    remove_whitespace,
    remove_whitespace_before_punctuation,
)

address_lines_1_to_6_keys = [
    # The API only accepts snake_case placeholders
    "address_line_1",
    "address_line_2",
    "address_line_3",
    "address_line_4",
    "address_line_5",
    "address_line_6",
]
address_lines_1_to_6_and_postcode_keys = address_lines_1_to_6_keys + ["postcode"]
address_line_7_key = "address_line_7"
address_lines_1_to_7_keys = address_lines_1_to_6_keys + [address_line_7_key]
country_UK = Country(UK)


class PostalAddress:
    MIN_LINES = 3
    MAX_LINES = 7
    INVALID_CHARACTERS_AT_START_OF_ADDRESS_LINE = r'@()=[]"\/,<>~'

    def __init__(self, raw_address, allow_international_letters=False):
        self.raw_address = raw_address
        self.allow_international_letters = allow_international_letters

        self._lines = [
            remove_whitespace_before_punctuation(line.rstrip(" ,"))
            for line in get_lines_with_normalised_whitespace(self.raw_address)
            if line.rstrip(" ,")
        ] or [""]

        self._bfpo_number, self._lines_without_bfpo = self._parse_and_extract_bfpo(self._lines)

        try:
            self.country = Country(self._lines_without_bfpo[-1])
            self._lines_without_country_or_bfpo = self._lines_without_bfpo[:-1]
        except CountryNotFoundError:
            self._lines_without_country_or_bfpo = self._lines_without_bfpo
            self.country = country_UK

    def __bool__(self):
        return bool(self.normalised)

    def __eq__(self, other):
        if not isinstance(other, PostalAddress):
            return False

        return (
            self.normalised_lines == other.normalised_lines
            and self.allow_international_letters == other.allow_international_letters
            and self.bfpo_number == other.bfpo_number
            and self.country == other.country
        )

    def __repr__(self):
        return f"{self.__class__.__name__}({repr(self.raw_address)})"

    def _parse_and_extract_bfpo(self, lines):
        bfpo_matcher = re.compile(r"^\s*bfpo\s*(?:c\/o)?(?:\s*(\d+))?\s*$")
        bfpo_number_line = next(
            filter(lambda line: bfpo_matcher.match(line.lower()) and bfpo_matcher.match(line.lower()).group(1), lines),
            None,
        )
        if not bfpo_number_line:
            return None, lines

        bfpo_number = bfpo_matcher.match(bfpo_number_line.lower()).group(1)
        lines = [line for line in lines if not bfpo_matcher.match(line.lower())]

        return int(bfpo_number), lines

    @classmethod
    def from_personalisation(cls, personalisation_dict, allow_international_letters=False):
        if address_line_7_key in personalisation_dict:
            keys = address_lines_1_to_6_keys + [address_line_7_key]
        else:
            keys = address_lines_1_to_6_and_postcode_keys
        return cls(
            "\n".join(str(personalisation_dict.get(key) or "") for key in keys),
            allow_international_letters=allow_international_letters,
        )

    @property
    def as_personalisation(self):
        bfpo_with_postcode = self.postcode and self.is_bfpo_address
        postcode_offset = 2 if bfpo_with_postcode else 1

        lines = dict.fromkeys(address_lines_1_to_6_keys, "")
        lines.update(
            {
                f"address_line_{index}": value
                for index, value in enumerate(self.normalised_lines[:-postcode_offset], start=1)
                if index < 7
            }
        )
        lines["postcode"] = lines["address_line_7"] = self.normalised_lines[-1]

        if bfpo_with_postcode:
            lines["postcode"] = lines["address_line_6"] = self.postcode or ""
        elif self.is_bfpo_address:
            lines["postcode"] = ""

        return lines

    @property
    def as_single_line(self):
        return ", ".join(self.normalised_lines)

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
            (self.allow_international_letters and self.international and not self.is_bfpo_address)
            or self.has_valid_postcode
            or (self.is_bfpo_address and not self.has_invalid_country_for_bfpo_address)
        )

    @property
    def has_invalid_characters(self):
        return any(
            line.startswith(tuple(self.INVALID_CHARACTERS_AT_START_OF_ADDRESS_LINE)) for line in self.normalised_lines
        )

    @property
    def has_no_fixed_abode_address(self):
        """
        We don't want users to sent to no fixed abode addresses, so validate that
        - no lines just consist of "NFA" (case insensitive)
        - the address does not contain "no fixed abode" or "no fixed address" (case insensitive)
        """
        if any(line.lower() == "nfa" for line in self.normalised_lines):
            return True
        if re.search(r"no fixed (abode|address)", self.normalised, re.IGNORECASE):
            return True
        return False

    @property
    def has_invalid_country_for_bfpo_address(self):
        """We don't want users to specify the country if they provide a BFPO number. Some BFPO numbers may resolve
        to non-UK addresses, but this will be handled as part of the BFPO delivery."""
        return self.international and self.is_bfpo_address

    @property
    def international(self):
        return self.postage != Postage.UK

    @property
    def is_bfpo_address(self):
        return self._bfpo_number is not None

    @property
    def bfpo_number(self):
        return self._bfpo_number

    @property
    def normalised(self):
        return "\n".join(self.normalised_lines)

    @property
    def normalised_lines(self):
        if self.is_bfpo_address:
            if self.international:
                return (
                    self._lines_without_country_or_bfpo + [f"BFPO {self._bfpo_number}"] + [self.country.canonical_name]
                )

            if self.postcode:
                # Replace the raw postcode with the normalised (eg uppercase with spaces) postcode
                return self._lines_without_country_or_bfpo[:-1] + [self.postcode] + [f"BFPO {self._bfpo_number}"]

            return self._lines_without_country_or_bfpo + [f"BFPO {self._bfpo_number}"]

        if self.international:
            return self._lines_without_country_or_bfpo + [self.country.canonical_name]

        if self.postcode:
            # Replace the raw postcode with the normalised (eg uppercase with spaces) postcode
            return self._lines_without_country_or_bfpo[:-1] + [self.postcode]

        return self._lines_without_country_or_bfpo

    @property
    def bfpo_address_lines(self):
        """Removes the postcode and BFPO footer lines for BFPO addresses"""
        if not self.is_bfpo_address:
            raise ValueError("Cannot be used for non-BFPO addresses")

        if self.postcode:
            return self.normalised_lines[:-2]

        return self.normalised_lines[:-1]

    @property
    def postage(self):
        return self.country.postage_zone

    @property
    def postcode(self):
        if self.international:
            return None
        return format_postcode_or_none(self._lines_without_country_or_bfpo[-1])

    @property
    def valid(self):
        return (
            self.has_valid_last_line
            and self.has_enough_lines
            and not self.has_too_many_lines
            and not self.has_invalid_characters
            and not (self.international and self.is_bfpo_address)
            and not self.has_no_fixed_abode_address
        )


def normalise_postcode(postcode):
    return remove_whitespace(postcode).upper()


def _is_a_real_uk_postcode(postcode):
    normalised = normalise_postcode(postcode)
    pattern = re.compile(rf"(({'|'.join(UK_POSTCODE_ZONES)})[0-9][0-9A-Z]?[0-9][A-BD-HJLNP-UW-Z]{{2}})")
    return bool(pattern.fullmatch(normalised))


def format_postcode_for_printing(postcode):
    """
    This function formats the postcode so that it is ready for automatic sorting by Royal Mail.
    :param String postcode: A postcode that's already been validated by _is_a_real_uk_postcode
    """
    postcode = normalise_postcode(postcode)
    return postcode[:-3] + " " + postcode[-3:]


# When processing an address we look at the postcode twice when
# normalising it, and once when validating it. So 8 is chosen because
# it’s 3, doubled to give some headroom then rounded up to the nearest
# power of 2
@lru_cache(maxsize=8)
def format_postcode_or_none(postcode):
    if _is_a_real_uk_postcode(postcode):
        return format_postcode_for_printing(postcode)
