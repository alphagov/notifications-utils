from functools import lru_cache

from notifications_utils.columns import Columns
from notifications_utils.sanitise_text import SanitiseASCII

from .data import (
    ADDITIONAL_SYNONYMS,
    COUNTRIES_AND_TERRITORIES,
    ROYAL_MAIL_EUROPEAN,
    UK_ISLANDS,
    UK_POSTAGE_REGIONS,
    Postage,
)


class CountryMapping(Columns):

    @staticmethod
    @lru_cache(maxsize=2048, typed=False)
    def make_key(original_key):

        original_key = original_key.replace('&', 'and')
        original_key = original_key.replace('+', 'and')

        normalised = "".join(
            character.lower() for character in original_key
            if character not in " _-',.()"
        )

        if '?' in SanitiseASCII.encode(normalised):
            return normalised

        return SanitiseASCII.encode(normalised)

    def __getitem__(self, key):
        try:
            return super().__getitem__(key)
        except KeyError:
            pass
        try:
            return super().__getitem__('the {}'.format(key))
        except KeyError:
            raise CountryNotFoundError(
                'Not a known country or territory ({})'.format(key)
            )


countries = CountryMapping(dict(
    COUNTRIES_AND_TERRITORIES + ADDITIONAL_SYNONYMS + UK_ISLANDS
))


class Country():

    def __init__(self, given_name):
        self.canonical_name = countries[given_name]

    @property
    def postage_zone(self):
        if self.canonical_name in UK_POSTAGE_REGIONS:
            return Postage.UK
        if self.canonical_name in ROYAL_MAIL_EUROPEAN:
            return Postage.EUROPE
        return Postage.REST_OF_WORLD


class CountryNotFoundError(KeyError):
    pass
