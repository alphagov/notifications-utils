import pytest

from notifications_utils.recipient_validation.email_address import validate_email_address
from notifications_utils.recipient_validation.errors import InvalidEmailError
from notifications_utils.recipients import allowed_to_send_to

valid_email_addresses = (
    "email@domain.com",
    "email@domain.COM",
    "firstname.lastname@domain.com",
    "firstname.o'lastname@domain.com",
    "email@subdomain.domain.com",
    "firstname+lastname@domain.com",
    "1234567890@domain.com",
    "email@domain-one.com",
    "_______@domain.com",
    "email@domain.name",
    "email@domain.superlongtld",
    "email@domain.co.jp",
    "firstname-lastname@domain.com",
    "info@german-financial-services.vermögensberatung",
    "info@german-financial-services.reallylongarbitrarytldthatiswaytoohugejustincase",
    "japanese-info@例え.テスト",
    "email@double--hyphen.com",
)
invalid_email_addresses = (
    "email@123.123.123.123",
    "email@[123.123.123.123]",
    "plainaddress",
    "@no-local-part.com",
    "Outlook Contact <outlook-contact@domain.com>",
    "no-at.domain.com",
    "no-tld@domain",
    ";beginning-semicolon@domain.co.uk",
    "middle-semicolon@domain.co;uk",
    "trailing-semicolon@domain.com;",
    '"email+leading-quotes@domain.com',
    'email+middle"-quotes@domain.com',
    '"quoted-local-part"@domain.com',
    '"quoted@domain.com"',
    "lots-of-dots@domain..gov..uk",
    "two-dots..in-local@domain.com",
    "multiple@domains@domain.com",
    "spaces in local@domain.com",
    "spaces-in-domain@dom ain.com",
    "underscores-in-domain@dom_ain.com",
    "pipe-in-domain@example.com|gov.uk",
    "comma,in-local@gov.uk",
    "comma-in-domain@domain,gov.uk",
    "pound-sign-in-local£@domain.com",
    "local-with-’-apostrophe@domain.com",
    "local-with-”-quotes@domain.com",
    "domain-starts-with-a-dot@.domain.com",
    "brackets(in)local@domain.com",
    f"email-too-long-{'a' * 320}@example.com",
    "incorrect-punycode@xn---something.com",
)


@pytest.mark.parametrize("email_address", valid_email_addresses)
def test_validate_email_address_accepts_valid(email_address):
    try:
        assert validate_email_address(email_address) == email_address
    except InvalidEmailError:
        pytest.fail("Unexpected InvalidEmailError")


@pytest.mark.parametrize(
    "email",
    [
        " email@domain.com ",
        "\temail@domain.com",
        "\temail@domain.com\n",
        "\u200bemail@domain.com\u200b",
    ],
)
def test_validate_email_address_strips_whitespace(email):
    assert validate_email_address(email) == "email@domain.com"


@pytest.mark.parametrize("email_address", invalid_email_addresses)
def test_validate_email_address_raises_for_invalid(email_address):
    with pytest.raises(InvalidEmailError) as e:
        validate_email_address(email_address)
    assert str(e.value) == "Not a valid email address"


@pytest.mark.parametrize("email_address", valid_email_addresses)
def test_validates_against_guestlist_of_email_addresses(email_address):
    assert not allowed_to_send_to(email_address, ["very_special_and_unique@example.com"])
