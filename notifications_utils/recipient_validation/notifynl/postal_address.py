import logging
import re
from functools import lru_cache

from notifications_utils.countries_nl import Country, CountryNotFoundError, Postage
from notifications_utils.formatters import (
    get_lines_with_normalised_whitespace,
    remove_whitespace,
    remove_whitespace_before_punctuation,
)

log = logging.getLogger(__name__)

country_NL = Country("Netherlands")
NL_POSTCODE_REGEX = r"\b[1-9][0-9]{3}\s?[A-Z]{2}\b"  # For finding a postcode inside a longer line
NL_POSTCODE_COMPACT_REGEX = r"[1-9][0-9]{3}[A-Z]{2}"  # For validating a compact, already-normalized string

address_lines_1_to_5_keys = [
    "address_line_1",
    "address_line_2",
    "address_line_3",
    "address_line_4",
    "address_line_5",
]
address_lines_1_to_5_and_postcode_keys = address_lines_1_to_5_keys + ["postcode"]
address_line_6_key = "address_line_6"
address_lines_1_to_6_keys = address_lines_1_to_5_keys + [address_line_6_key]


class NonDutchPostalCodeError(Exception):
    pass


class MissingCityError(Exception):
    pass


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

    postcode = match.group().upper()  # uppercased postcode
    before = line[: match.start()].strip()
    after = line[match.end() :].strip()
    return before, after, postcode


def normalise_postcode(postcode):
    return remove_whitespace(postcode).upper()


def _is_a_real_nl_postcode(postcode):
    normalised = normalise_postcode(postcode)
    pattern = re.compile(rf"{NL_POSTCODE_COMPACT_REGEX}")
    return bool(pattern.fullmatch(normalised))


def format_postcode_for_printing(postcode):
    """
    This function formats the postcode so that it is ready for automatic sorting by PostNL.
    :param String postcode: A postcode that's already been validated by _is_a_real_nl_postcode
    """
    postcode = normalise_postcode(postcode)
    return f"{postcode[:4]} {postcode[4:]}"


# When processing an address we look at the postcode twice when
# normalising it, and once when validating it. So 8 is chosen because
# it’s 3, doubled to give some headroom then rounded up to the nearest
# power of 2
@lru_cache(maxsize=8)
def format_nl_postcode_or_none(postcode):
    if _is_a_real_nl_postcode(postcode):
        return format_postcode_for_printing(postcode)


def country_is_netherlands(country):
    if str(country).lower() in ("netherlands", "nederland"):
        return True


class PostalAddress:
    MIN_LINES = 3  # name / street address/ postcode and city
    MAX_LINES = 6
    INVALID_CHARACTERS_AT_START_OF_ADDRESS_LINE = r'@()=[]"\/,<>~'

    def __init__(self, raw_address=None, address=None, allow_international_letters=False):
        self._country = None
        self._to_delete_city_line_index = None
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
        if self.international:
            return None
        for line in reversed(self._lines):
            _, _, postcode = split_postcode_line(line)
            if postcode:
                return format_nl_postcode_or_none(postcode)
        return None

    # ---------------------------------------------------------
    # CITY (if found on the same line as postcode)
    # ---------------------------------------------------------
    @property
    def city(self):
        for i, line in enumerate(self._lines):
            before, after, postcode = split_postcode_line(line)
            if postcode:
                if before and not is_country_string(before):
                    return before.strip()

                if after and not is_country_string(after):
                    return after.strip()

                # fallback: next line
                if i + 1 < len(self._lines):
                    next_line = self._lines[i + 1].strip()
                    if next_line and not is_country_string(next_line):
                        self._to_delete_city_line_index = i + 1  # mark line for deletion
                        return next_line.strip()

        return None

    # ---------------------------------------------------------
    # NORMALISATION
    # ---------------------------------------------------------

    @classmethod
    def from_personalisation(cls, personalisation_dict, allow_international_letters=False):
        if address_line_6_key in personalisation_dict:
            keys = address_lines_1_to_5_keys + [address_line_6_key]
        else:
            keys = address_lines_1_to_5_and_postcode_keys

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
    def as_personalisation(self):
        lines = dict.fromkeys(address_lines_1_to_5_keys, "")
        normalised_full = self.normalised_lines or []
        last_line = normalised_full[-1]
        normalised = normalised_full[:-1]

        # Fill address_line_1 .. address_line_5
        for index, value in enumerate(normalised[:5], start=1):
            lines[f"address_line_{index}"] = value

        if not self.international:
            lines["postcode"] = self.postcode or ""

        lines["address_line_6"] = last_line

        return lines

    @property
    def normalised_lines(self):
        lines = list(self._lines)
        postcode = self.postcode
        city = self.city.strip().upper() if self.city else None

        if not lines:
            return []

        # If the address is international or there is no postcode found (NL postcode),
        # stop with the normalization and return all non-empty address lines
        if self.has_valid_international_address:
            cleaned = [line.strip() for line in lines if line.strip()]

            if cleaned and self.country:
                cleaned[-1] = self.country.canonical_name

            return cleaned
        if self.has_valid_local_address:
            # only for NL addresses
            # remove the city-only line (deleted first so the index is correct)
            if self._to_delete_city_line_index is not None and self._to_delete_city_line_index < len(lines):
                del lines[self._to_delete_city_line_index]

            # remove postcode line
            lines = [line for line in lines if not re.search(NL_POSTCODE_REGEX, line, flags=re.IGNORECASE)]

            # remove Netherlands country lines
            lines = [line for line in lines if line.lower() not in ("netherlands", "nederland", "the netherlands")]

            # strip all remaining lines
            cleaned_lines = [line.strip() for line in lines if line.strip()]

            # append formatted postcode + city
            if cleaned_lines and city:
                # recomended by postNL double spacing between postode and city
                # do not remove the extraspace after the postode
                cleaned_lines.append(f"{postcode}  {city}")
            else:
                cleaned_lines.append(postcode)

            return cleaned_lines
        return lines

    @property
    def normalised(self):
        return "\n".join(self.normalised_lines)

    @property
    def as_single_line(self):
        return ", ".join(self.normalised_lines)

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
        if not self.allow_international_letters:
            return False
        country = getattr(self, "country", None)
        if not country:
            return False
        return country.postage_zone != Postage.NL

    @property
    def has_valid_local_or_international_address(self):
        if self.international:
            return self.has_valid_international_address
        else:
            return self.has_valid_local_address

    @property
    def has_valid_last_line(self):
        if self.international:
            return is_country_string(self.last_line)
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
