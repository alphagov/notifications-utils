import logging
import re
from functools import lru_cache

from notifications_utils.countries import Country, CountryNotFoundError

from ..postal_address import PostalAddress as PostalAddressUK
from ..postal_address import normalise_postcode

log = logging.getLogger(__name__)
country_NL = Country("Netherlands")
NL_POSTCODE_REGEX = r"\b[1-9][0-9]{3}\s?[A-Z]{2}\b"


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


def _is_a_real_nl_postcode(postcode):
    if not postcode:
        return False

    postcode = postcode.strip().upper()
    return bool(re.fullmatch(NL_POSTCODE_REGEX, postcode.replace(" ", "")))


def format_postcode_for_printing(postcode):
    postcode = normalise_postcode(postcode)
    return postcode[:4] + " " + postcode[4:]


@lru_cache(maxsize=8)
def format_postcode_or_none(postcode):
    if _is_a_real_nl_postcode(postcode):
        return format_postcode_for_printing(postcode)


class PostalAddress(PostalAddressUK):
    MIN_LINES = 2

    def __init__(self, address: str | list, allow_international_letters: bool = True):
        if isinstance(address, list):
            address: str = "\n".join(address)

        super().__init__(address, allow_international_letters)

        try:
            self.country = Country(self._lines_without_bfpo[-1])
            self._lines_without_country_or_bfpo = self._lines_without_bfpo[:-1]
        except CountryNotFoundError:
            self._lines_without_country_or_bfpo = self._lines_without_bfpo
            self.country = country_NL

    @property
    def postcode(self):
        if not self._lines_without_country_or_bfpo:
            log.warning("Postcode line not found")
            return None

        # scan lines in reverse
        for line in reversed(self._lines_without_country_or_bfpo):
            line_upper = line.upper()
            match = re.search(NL_POSTCODE_REGEX, line_upper)
            if match:
                normalized = match.group(0).replace(" ", "")
                return normalized[:4] + " " + normalized[4:]

        log.warning("No valid NL postcode found in address lines: %s", self._lines_without_country_or_bfpo)
        return None
