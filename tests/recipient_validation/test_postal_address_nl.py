import pytest

from notifications_utils.recipient_validation.notifynl.postal_address import PostalAddressNL, country_NL

# -----------------------------------------------------
# BASIC POSTCODE PARSING
# -----------------------------------------------------


@pytest.mark.parametrize(
    "address, expected",
    [
        ("Kalverstraat 1\n1012NX Amsterdam", "1012 NX"),
        ("Kalverstraat 1\n1012 nx Amsterdam", "1012 NX"),
        ("Kalverstraat 1\n1012  NX Amsterdam", "1012 NX"),
        (["Kalverstraat 1", "1012NX Amsterdam"], "1012 NX"),
    ],
)
def test_nl_postcode_parsing(address, expected):
    pa = PostalAddressNL(address)
    assert pa.postcode == expected


def test_no_postcode_returns_none():
    pa = PostalAddressNL("Kalverstraat 1\nAmsterdam")
    assert pa.postcode is None


# -----------------------------------------------------
# COUNTRY DETECTION
# -----------------------------------------------------


def test_default_country_is_nl():
    pa = PostalAddressNL("Kalverstraat 1\n1012NX Amsterdam")
    assert pa.country == country_NL


def test_explicit_country_overrides_default():
    pa = PostalAddressNL("Kalverstraat 1\n1012NX\nNetherlands")
    assert pa.country.canonical_name.lower() == "netherlands"


# -----------------------------------------------------
# NORMALISATION
# -----------------------------------------------------


def test_normalised_lines_replaces_last_line_with_postcode():
    pa = PostalAddressNL("Kalverstraat 1\n1012nx Amsterdam")
    assert pa.normalised_lines[-1] == "1012 NX"


def test_normalised_lines_keeps_other_lines():
    pa = PostalAddressNL("A\nB\n1012NX Amsterdam")
    assert pa.normalised_lines == ["A", "B", "1012 NX"]


# -----------------------------------------------------
# VALIDATION RULES
# -----------------------------------------------------


def test_valid_address():
    pa = PostalAddressNL("Kalverstraat 1\n1012NX Amsterdam")
    assert pa.valid is True


def test_invalid_without_postcode():
    pa = PostalAddressNL("Kalverstraat 1\nAmsterdam")
    assert pa.valid is False


def test_too_few_lines():
    pa = PostalAddressNL("1012NX")
    assert pa.has_enough_lines is False
    assert pa.valid is False


def test_too_many_lines():
    pa = PostalAddressNL("\n".join(["Line1", "Line2", "Line3", "Line4", "Line5", "Line6", "Line7", "1012NX"]))
    assert pa.has_too_many_lines is True
    assert pa.valid is False


# -----------------------------------------------------
# INVALID CHARACTERS
# -----------------------------------------------------


@pytest.mark.parametrize(
    "line",
    [
        "@Weird start",
        "(Bad format street",
        "[Bracket street",
    ],
)
def test_invalid_characters(line):
    pa = PostalAddressNL(f"{line}\n1012NX Amsterdam")
    assert pa.has_invalid_characters is True
    assert pa.valid is False


# -----------------------------------------------------
# SPECIAL CASES
# -----------------------------------------------------


def test_address_as_list():
    pa = PostalAddressNL(["Kalverstraat 1", "1012NX Amsterdam"])
    assert pa.postcode == "1012 NX"


def test_mixed_case_and_spacing():
    pa = PostalAddressNL("Kalverstraat 1 \n  1012  nx   Amsterdam  ")
    assert pa.postcode == "1012 NX"


def test_does_not_treat_bfpo_as_special():
    pa = PostalAddressNL("BFPO 123\n1012NX Amsterdam")
    # UK class would mark this as BFPO; NL must ignore
    assert not getattr(pa, "is_bfpo_address", False)
    assert pa.postcode == "1012 NX"
    assert pa.valid is True
