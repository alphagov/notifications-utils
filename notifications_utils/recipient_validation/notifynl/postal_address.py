import logging
import re

from notifications_utils.countries import Country, CountryNotFoundError

from ..postal_address import PostalAddress as PostalAddressUK

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


class PostalAddress(PostalAddressUK):
    MIN_LINES = 2
    MAX_LINES = 7  # same shape for template compatibility

    def __init__(self, address: str | list, allow_international_letters: bool = False):
        if isinstance(address, list):
            address = "\n".join(address)

        # Disable UK BFPO parsing before parent init
        self._bfpo_number = None
        self._lines_without_bfpo = []

        super().__init__(address, allow_international_letters)

        # Reinterpret the last line as NL (UK parent assumes UK)
        try:
            detected_country = Country(self._lines_without_bfpo[-1])
            if str(detected_country).lower() not in ("netherlands", "nederland"):
                self.country = detected_country
                self._lines_without_country_or_bfpo = self._lines_without_bfpo[:-1]
            else:
                self.country = country_NL
                self._lines_without_country_or_bfpo = self._lines_without_bfpo
        except CountryNotFoundError:
            self.country = country_NL
            self._lines_without_country_or_bfpo = self._lines_without_bfpo

    # ---------------------------------------------------------
    # NL POSTCODE OVERRIDE
    # ---------------------------------------------------------
    @property
    def postcode(self):
        if not self._lines_without_country_or_bfpo:
            return None

        for line in reversed(self._lines_without_country_or_bfpo):
            match = re.search(NL_POSTCODE_REGEX, line.upper())
            if match:
                cleaned = match.group(0).replace(" ", "")
                return cleaned[:4] + " " + cleaned[4:]

        return None

    # ---------------------------------------------------------
    # OVERRIDE UK BFPO LOGIC
    # ---------------------------------------------------------
    def _parse_and_extract_bfpo(self, lines):
        # NL does not use BFPO → ignore completely
        return None, lines

    @property
    def is_bfpo_address(self) -> bool:
        return False

    @property
    def bfpo_number(self):
        return None

    @property
    def has_no_fixed_abode_address(self) -> bool:
        return False

    # ---------------------------------------------------------
    # NL SPECIFIC OVERRIDES
    # ---------------------------------------------------------
    @property
    def has_valid_last_line(self):
        return self.postcode is not None

    @property
    def normalised_lines(self):
        base = list(self._lines_without_country_or_bfpo)
        if self.postcode:
            return base[:-1] + [self.postcode]
        return base

    @property
    def valid(self):
        return (
            self.has_enough_lines
            and not self.has_too_many_lines
            and not self.has_invalid_characters
            and not self.has_no_fixed_abode_address
            and self.postcode is not None
        )
