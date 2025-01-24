import pytest

from notifications_utils.international_billing_rates import (
    COUNTRY_PREFIXES,
    INTERNATIONAL_BILLING_RATES,
)
from notifications_utils.recipient_validation.phone_number import PhoneNumber


def test_international_billing_rates_exists():
    assert INTERNATIONAL_BILLING_RATES["1"]["names"][0] == "Canada"


@pytest.mark.parametrize("country_prefix, values", sorted(INTERNATIONAL_BILLING_RATES.items()))
def test_international_billing_rates_are_in_correct_format(country_prefix, values):
    assert isinstance(country_prefix, str)
    # we don't want the prefixes to have + at the beginning for instance
    assert country_prefix.isdigit()

    assert set(values.keys()) == {"attributes", "rate_multiplier", "names"}

    assert isinstance(values["rate_multiplier"], int)
    assert 1 <= values["rate_multiplier"] <= 4

    assert isinstance(values["names"], list)
    assert all(isinstance(country, str) for country in values["names"])

    assert isinstance(values["attributes"], dict)
    assert values["attributes"]["dlr"] is None or isinstance(values["attributes"]["dlr"], str)


def test_country_codes():
    assert len(COUNTRY_PREFIXES) == 220


@pytest.mark.parametrize(
    "number, expected",
    [
        ("48122014001", False),  # Poland alpha: Yes
        ("1-416-869-3457", True),  # Canada alpha: No
        ("40213120301", False),  # Romania alpha: REG
        ("+60123451345", True),
    ],
)  # Malaysia alpha: NO
def test_use_numeric_sender(number, expected):
    number = PhoneNumber(number)
    assert number.should_use_numeric_sender() == expected
    # assert use_numeric_sender(number) == expected
