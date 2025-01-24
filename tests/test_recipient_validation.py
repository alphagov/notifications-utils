import pytest

from notifications_utils.recipients import format_recipient


@pytest.mark.parametrize(
    "recipient, expected_formatted",
    [
        (True, ""),
        (False, ""),
        (0, ""),
        (0.1, ""),
        (None, ""),
        ("foo", "foo"),
        ("TeSt@ExAmPl3.com", "test@exampl3.com"),
        ("+4407900 900 123", "447900900123"),
        ("+1 202-555-0104", "12025550104"),
    ],
)
def test_format_recipient(recipient, expected_formatted):
    assert format_recipient(recipient) == expected_formatted
