from notifications_utils.countries import Country as BaseCountry
from notifications_utils.countries import CountryMapping as BaseCountryMapping
from notifications_utils.countries import CountryNotFoundError as BaseCountryNotFoundError
from notifications_utils.countries.data import (
    ADDITIONAL_SYNONYMS,
    COUNTRIES_AND_TERRITORIES,
    EUROPEAN_ISLANDS,
    ROYAL_MAIL_EUROPEAN,
    UK_ISLANDS,
    WELSH_NAMES,
)


class Postage:
    # FIRST = "netherlands"
    # SECOND = "netherlands"
    # ECONOMY = "netherlands"
    NL = "netherlands"
    EUROPE = "europe"
    REST_OF_WORLD = "rest-of-world"


class CountryMapping(BaseCountryMapping):
    pass


countries = CountryMapping(
    dict(COUNTRIES_AND_TERRITORIES + UK_ISLANDS + EUROPEAN_ISLANDS + WELSH_NAMES + ADDITIONAL_SYNONYMS)
)


class Country(BaseCountry):
    @property
    def postage_zone(self):
        if self.canonical_name.lower() in ("netherlands", "nederland"):
            return Postage.NL  # or whatever zone you want
        if self.canonical_name in ROYAL_MAIL_EUROPEAN:
            return Postage.EUROPE
        if self.canonical_name in EUROPEAN_ISLANDS:
            return Postage.EUROPE
        return Postage.REST_OF_WORLD


class CountryNotFoundError(BaseCountryNotFoundError):
    pass
