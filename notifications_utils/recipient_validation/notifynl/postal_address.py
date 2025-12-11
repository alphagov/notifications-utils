import logging
import re

from notifications_utils.countries_nl import Country, CountryNotFoundError, Postage

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
    MAX_LINES = 7  # template compatibility

    def __init__(self, raw_address=None, address=None, allow_international_letters=False):
        # Match UK behaviour exactly
        if address is None:
            address = raw_address

        if isinstance(address, list):
            address = "\n".join(address)

        # Disable UK BFPO parsing before parent init
        self._bfpo_number = None
        self._lines_without_bfpo = []

        super().__init__(address, allow_international_letters)

        # Reinterpret last line as NL (UK parent assumes UK)
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

        # Search lines in reverse order for postcode
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
        # NL ignores BFPO completely
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
    def international(self):
        return self.postage != Postage.NL

    @property
    def normalised_lines(self):
        """
        Rebuild NL address lines:
        - Strip country if present in last line
        - Keep postcode + city on last line
        - Remove empty lines
        """
        lines = list(self._lines_without_country_or_bfpo)

        if not lines:
            return []

        postcode = self.postcode
        if postcode:
            new_lines = []
            # Remove postcode from any line to avoid duplication
            for line in lines:
                line = re.sub(NL_POSTCODE_REGEX, "", line, flags=re.IGNORECASE).strip()
                # Skip empty lines and country lines
                if line and line.lower() not in ("netherlands", "nederland"):
                    new_lines.append(line)

            if new_lines:
                # Pop last line as city (or last meaningful line)
                city_line = new_lines.pop(-1)
                last_line = f"{postcode} {city_line}".strip()
            else:
                last_line = postcode

            new_lines.append(last_line)
            return new_lines

        return [line.strip() for line in lines if line.strip()]

    @property
    def valid(self):
        return (
            self.has_enough_lines
            and not self.has_too_many_lines
            and not self.has_invalid_characters
            and not self.has_no_fixed_abode_address
            and self.postcode is not None
        )
