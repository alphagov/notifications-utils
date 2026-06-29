from functools import lru_cache

from notifications_utils.insensitive_dict import InsensitiveDict
from notifications_utils.sanitise_text import SanitiseASCII

from .data import (
    ADDITIONAL_SYNONYMS,
    COUNTRIES_AND_TERRITORIES,
    EUROPEAN_ISLANDS,
    ROYAL_MAIL_EUROPEAN,
    UK,
    UK_ISLANDS,
    WELSH_NAMES,
    Postage,
)


class CountryMapping(InsensitiveDict):
    @staticmethod
    @lru_cache(maxsize=2048, typed=False)
    def make_key(original_key: str) -> str:
        original_key = original_key.replace("&", "and")
        original_key = original_key.replace("+", "and")

        normalised = "".join(character.lower() for character in original_key if character not in " _-'’,.()")

        if "?" in SanitiseASCII.encode(normalised):
            return normalised

        return SanitiseASCII.encode(normalised)

    def __contains__(self, key: object) -> bool:
        if isinstance(key, str) and any(c.isdigit() for c in key):
            # A string with a digit can’t be a country and is probably a
            # postcode, so let’s do a little optimisation, skip the
            # expensive string manipulation to normalise the key and say
            # that there’s no matching country
            return False
        return super().__contains__(key)

    def __getitem__(self, key: str) -> str:
        for key_ in (key, f"the {key}", f"yr {key}", f"y {key}"):
            if key_ in self:
                return super().__getitem__(key_)

        raise CountryNotFoundError(f"Not a known country or territory ({key})")


countries = CountryMapping(
    dict(COUNTRIES_AND_TERRITORIES + UK_ISLANDS + EUROPEAN_ISLANDS + WELSH_NAMES + ADDITIONAL_SYNONYMS)
)


class Country:
    canonical_name: str

    def __init__(self, given_name: str):
        self.canonical_name = countries[given_name]

    def __eq__(self, other) -> bool:
        return self.canonical_name == other.canonical_name

    @property
    def postage_zone(self) -> str:
        if self.canonical_name == UK:
            return Postage.UK
        if self.canonical_name in ROYAL_MAIL_EUROPEAN:
            return Postage.EUROPE
        return Postage.REST_OF_WORLD


class CountryNotFoundError(KeyError):
    pass
