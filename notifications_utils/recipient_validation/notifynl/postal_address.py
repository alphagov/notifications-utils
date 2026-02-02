import logging
import re

from notifications_utils.countries_nl import Country, CountryNotFoundError, Postage
from notifications_utils.formatters import (
    get_lines_with_normalised_whitespace,
    remove_whitespace_before_punctuation,
)

log = logging.getLogger(__name__)

country_NL = Country("Netherlands")
NL_POSTCODE_REGEX = r"\b[1-9][0-9]{3}\s?[A-Z]{2}\b"


address_lines_1_to_6_keys = [
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


class NonDutchPostalCodeError(Exception):
    pass


class MissingCityError(Exception):
    pass


def _is_a_real_nl_postcode(postcode: str) -> bool:
    if not postcode or "\u00a0" in postcode:
        return False
    return bool(re.fullmatch(NL_POSTCODE_REGEX, postcode.strip(), re.IGNORECASE))


def has_nl_postcode(lines):
    return any(re.search(NL_POSTCODE_REGEX, line, flags=re.IGNORECASE) for line in lines)


def is_country_string(value):
    try:
        Country(value)
        return True
    except Exception:
        return False


def split_postcode_line(line):
    match = re.search(NL_POSTCODE_REGEX, line, flags=re.IGNORECASE)
    if not match:
        return None, None, None  # before, after, postcode

    postcode = match.group().upper()  # normalized postcode
    before = line[: match.start()].strip()
    after = line[match.end() :].strip()
    return before, after, postcode


def country_is_netherlands(country):
    if str(country).lower() in ("netherlands", "nederland"):
        return True


class PostalAddress:
    MIN_LINES = 3  # name / street address/ postcode and city
    MAX_LINES = 7  # template compatibility
    INVALID_CHARACTERS_AT_START_OF_ADDRESS_LINE = r'@()=[]"\/,<>~'

    def __init__(self, raw_address=None, address=None, allow_international_letters=False):
        self._country = None
        self.allow_international_letters = allow_international_letters

        if address is None:
            address = raw_address

        if isinstance(address, list):
            address = "\n".join(address)

        self.raw_address = address or ""

        self._lines = [
            remove_whitespace_before_punctuation(line.rstrip(" ,"))
            for line in get_lines_with_normalised_whitespace(self.raw_address)
            if line.rstrip(" ,")
        ] or [""]

        # -----------------------------------------------------
        # BFPO: fully disabled
        # -----------------------------------------------------
        self._bfpo_number = None

        # -----------------------------------------------------
        # get last line should be a Country (defaults to NL)
        # -----------------------------------------------------
        self.last_line = self._lines[-1].strip()

    def __bool__(self):
        return bool(self.normalised)

    def __eq__(self, other):
        if not isinstance(other, PostalAddress):
            return False

        return (
            self.normalised_lines == other.normalised_lines
            and self.allow_international_letters == other.allow_international_letters
            and self.country == other.country
            and self.city == other.city
            and self.postage == other.postage
            and self.postcode == other.postcode
        )

    def __repr__(self):
        return f"{self.__class__.__name__}({repr(self.raw_address)})"

    # ---------------------------------------------------------
    # Country
    # ---------------------------------------------------------
    @property
    def country(self):
        if self._country is not None:
            return self._country

        try:
            self._country = Country(self.last_line)
        except CountryNotFoundError:
            # default to NL if last line is not a country
            self._country = country_NL

        return self._country

    # ---------------------------------------------------------
    # POSTCODE - (NL match)
    # ---------------------------------------------------------
    @property
    def postcode(self):
        for line in reversed(self._lines):
            match = re.search(NL_POSTCODE_REGEX, line.upper())
            if match:
                cleaned = match.group(0).replace(" ", "")
                return f"{cleaned[:4]} {cleaned[4:]}"

        return None

    # ---------------------------------------------------------
    # CITY (if found on the same line as postcode)
    # ---------------------------------------------------------
    @property
    def city(self):
        for line in self._lines:
            # detect postcode and city line
            if has_nl_postcode([line]):  # already case-insensitive
                # check if the city is next to postcode
                before, after, _postcode = split_postcode_line(line)
                city_candidate = before or after
                # city_candidate string must NOT be a country
                if city_candidate and not is_country_string(city_candidate):
                    return city_candidate
        return None

    # ---------------------------------------------------------
    # NORMALISATION
    # ---------------------------------------------------------

    @classmethod
    def from_personalisation(cls, personalisation_dict, allow_international_letters=False):
        if address_line_7_key in personalisation_dict:
            keys = address_lines_1_to_6_keys + [address_line_7_key]
        else:
            keys = address_lines_1_to_6_and_postcode_keys

        address = "\n".join(
            str(personalisation_dict.get(key) or "").strip()
            for key in keys
            if str(personalisation_dict.get(key) or "").strip()
        )

        return cls(
            address=address,
            allow_international_letters=allow_international_letters,
        )

    @property
    def normalised_lines(self):
        lines = list(self._lines)

        if not lines:
            return []

        international = self.international
        postcode = self.postcode

        # If the address is international or there is no postcode found (NL postcode),
        # stop with the normalization and return all non-empty address lines
        if not postcode or international:
            return [line.strip() for line in lines if line.strip()]

        # only for NL addresses
        cleaned_lines = []
        for line in lines:
            # Remove the line with the NLpostcode to be Replaced with the normalised (eg uppercase with spaces)
            if re.search(NL_POSTCODE_REGEX, line, flags=re.IGNORECASE):
                continue

            # Remove netherlands from the lines (and invalid lines)
            if not line or line.lower() in ("netherlands", "nederland", "the netherlands"):
                continue

            cleaned_lines.append(line)

        if cleaned_lines:
            # recomended by postNL double spacing between postode and city
            # do not remove the extraspace after the postode
            cleaned_lines.append(f"{postcode}\u00a0\u00a0{self.city}")
        else:
            cleaned_lines.append(postcode)

        return cleaned_lines

    @property
    def normalised(self):
        return "\n".join(self.normalised_lines)

    # ---------------------------------------------------------
    # POSTAGE / INTERNATIONAL
    # ---------------------------------------------------------
    @property
    def postage(self):
        return self.country.postage_zone

    @property
    def international(self):
        return self.postage != Postage.NL

    # ---------------------------------------------------------
    # VALIDATION
    # ---------------------------------------------------------
    @property
    def line_count(self):
        return len(self.normalised_lines)

    @property
    def has_enough_lines(self):
        return self.line_count >= self.MIN_LINES

    @property
    def has_too_many_lines(self):
        return self.line_count > self.MAX_LINES

    @property
    def has_invalid_characters(self):
        return any(
            line.startswith(tuple(self.INVALID_CHARACTERS_AT_START_OF_ADDRESS_LINE)) for line in self.normalised_lines
        )

    @property
    def has_no_fixed_abode_address(self):
        return False

    @property
    def has_invalid_country_for_bfpo_address(self):
        return False

    @property
    def has_country_as_last_line(self):
        detected_country = Country(self.last_line)
        if detected_country:
            return True
        else:
            return False

    @property
    def has_valid_local_address(self):
        return bool(self.postcode and self.city)

    @property
    def has_valid_international_address(self):
        has_country = bool(getattr(self, "country", None))
        allows_international = self.allow_international_letters
        return allows_international and has_country

    @property
    def has_valid_local_or_international_address(self):
        if self.international:
            return self.has_valid_international_address
        else:
            return self.has_valid_local_address

    # ---------------------------------------------------------
    # FINAL VALID FLAG
    # ---------------------------------------------------------
    @property
    def valid(self):
        return (
            self.has_enough_lines
            and self.has_valid_local_or_international_address
            and not self.has_too_many_lines
            and not self.has_invalid_characters
        )

    # ---------------------------------------------------------
    # BFPO PUBLIC SURFACE (graceful no-ops)
    # ---------------------------------------------------------
    @property
    def is_bfpo_address(self):
        return False

    @property
    def bfpo_number(self):
        return None

    @property
    def bfpo_address_lines(self):
        return []
