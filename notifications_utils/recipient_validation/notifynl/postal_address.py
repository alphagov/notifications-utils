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


class PostalAddress:
    MIN_LINES = 2
    MAX_LINES = 7  # template compatibility
    INVALID_CHARACTERS_AT_START_OF_ADDRESS_LINE = r'@()=[]"\/,<>~'

    def __init__(self, raw_address=None, address=None, allow_international_letters=False):
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
        # BFPO: fully disabled (no parsing, no state)
        # -----------------------------------------------------
        self._bfpo_number = None
        self._lines_without_bfpo = self._lines

        # -----------------------------------------------------
        # Country detection (default to NL, skip postcodes)
        # -----------------------------------------------------
        last_line = self._lines_without_bfpo[-1].strip()

        # If empty → default NL
        if not last_line:
            self.country = country_NL
            self._lines_without_country_or_bfpo = self._lines_without_bfpo

        # If last line is an NL postcode → default NL
        elif re.fullmatch(NL_POSTCODE_REGEX, last_line):
            self.country = country_NL
            self._lines_without_country_or_bfpo = self._lines_without_bfpo

        # Otherwise, attempt country detection
        else:
            try:
                detected_country = Country(last_line)
                if str(detected_country).lower() in ("netherlands", "nederland"):
                    self.country = country_NL
                    self._lines_without_country_or_bfpo = self._lines_without_bfpo
                else:
                    self.country = detected_country
                    self._lines_without_country_or_bfpo = self._lines_without_bfpo[:-1]
            except CountryNotFoundError:
                # Not a country → treat as address, default NL
                self.country = country_NL
                self._lines_without_country_or_bfpo = self._lines_without_bfpo

    # ---------------------------------------------------------
    # NL POSTCODE
    # ---------------------------------------------------------
    @property
    def postcode(self):
        for line in reversed(self._lines_without_country_or_bfpo):
            match = re.search(NL_POSTCODE_REGEX, line.upper())
            if match:
                cleaned = match.group(0).replace(" ", "")
                return f"{cleaned[:4]} {cleaned[4:]}"
        return None

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
        lines = list(self._lines_without_country_or_bfpo)

        if not lines:
            return []

        postcode = self.postcode
        if not postcode:
            return [line.strip() for line in lines if line.strip()]

        cleaned_lines = []
        for line in lines:
            line = re.sub(NL_POSTCODE_REGEX, "", line, flags=re.IGNORECASE).strip()
            if line and line.lower() not in ("netherlands", "nederland"):
                cleaned_lines.append(line)

        if cleaned_lines:
            city = cleaned_lines.pop(-1)
            # recomended by postNL double spacing between postode and city
            # do not remove the extraspace after the postode
            cleaned_lines.append(f"{postcode}\u00a0\u00a0{city}")
        else:
            cleaned_lines.append(postcode)

        return cleaned_lines

    @property
    def normalised(self):
        return "\n".join(self.normalised_lines)

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
        # if any(line.lower() == "nfa" for line in self.normalised_lines):
        #     return True
        # if re.search(r"no fixed (abode|address)", self.normalised, re.IGNORECASE):
        #     return True
        return False

    @property
    def has_valid_last_line(self):
        return self.postcode is not None

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
    # FINAL VALID FLAG
    # ---------------------------------------------------------
    @property
    def valid(self):
        return (
            self.has_enough_lines
            and not self.has_too_many_lines
            and not self.has_invalid_characters
            and not self.has_no_fixed_abode_address
            and self.postcode is not None
        )
