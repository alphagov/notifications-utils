from functools import partial
from random import choice, randrange
from unittest.mock import Mock

import pytest

from notifications_utils.countries_nl import Country
from notifications_utils.qr_code import QrCodeTooLong
from notifications_utils.recipients import (
    RecipientCSV,
    first_column_headings,
)
from notifications_utils.template import (
    HTMLEmailTemplate,
    LetterPreviewTemplate,
    SMSMessageTemplate,
)


def _sample_template(template_type, content="foo"):
    return {
        "email": HTMLEmailTemplate({"content": content, "subject": "bar", "template_type": "email"}),
        "sms": SMSMessageTemplate({"content": content, "template_type": "sms"}),
        "letter": LetterPreviewTemplate(
            {"content": content, "subject": "bar", "template_type": "letter"},
        ),
    }.get(template_type)


def _index_rows(rows):
    return {row.index for row in rows}


@pytest.mark.parametrize(
    "file_contents,template_type,rows_with_bad_recipients,rows_with_missing_data",
    [
        (
            # missing postcode
            """
                address_line_1,address_line_2,address_line_3,address_line_4,address_line_5,postcode,date
                name,          building,      street,        town,          county,        2552HN Den Haag, today
                name,          building,      street,        town,          county,        ,        today
            """,
            "letter",
            {1},
            set(),
        ),
        (
            # not enough address fields
            """
                address_line_1, postcode, date
                name,           2552HN den Haag, today
            """,
            "letter",
            {0},
            set(),
        ),
        (
            # optional address fields not filled in
            """
                address_line_1,address_line_2,address_line_3,address_line_4,address_line_5,postcode,date
                name          ,123 fake st.  ,              ,              ,              ,2552HN Den Haag,today
                name          ,              ,              ,              ,              ,2552HN Den Haag,today
            """,
            "letter",
            {1},
            set(),
        ),
        (
            # Can use any address columns
            """
                address_line_3, address_line_4, address_line_5,  date
                name,           123 fake st.,   2552HN Den Haag, today
            """,
            "letter",
            set(),
            set(),
        ),
        (
            """
                telefoonnummer,name,date
                07700900460,test1,test1
                07700900460,test1
                +44 123,test1,test1
                07700900460,test1,test1
                07700900460,test1
                +1644000000,test1,test1
                ,test1,test1
            """,
            "sms",
            {2, 5},
            {1, 4, 6},
        ),
        (
            """
                telefoonnummer,name
                07700900460,test1,test2
            """,
            "sms",
            set(),
            set(),
        ),
        (
            """
            """,
            "sms",
            set(),
            set(),
        ),
        (
            """
                ,,,,,,,,,telefoonnummer
                ,,,,,,,,,07700900100
                ,,,,,,,,,07700900100
            """,
            "sms",
            set(),
            set(),
        ),
    ],
)
@pytest.mark.parametrize(
    "partial_instance",
    [
        partial(RecipientCSV),
    ],
)
def test_bad_or_missing_data(
    file_contents, template_type, rows_with_bad_recipients, rows_with_missing_data, partial_instance
):
    recipients = partial_instance(file_contents, template=_sample_template(template_type, "((date))"))
    rows_with_errors_index = _index_rows(recipients.rows_with_bad_recipients)
    assert rows_with_errors_index == rows_with_bad_recipients
    rows_with_missing_data_index = _index_rows(recipients.rows_with_missing_data)
    assert rows_with_missing_data_index == rows_with_missing_data
    if rows_with_bad_recipients or rows_with_missing_data:
        assert recipients.has_errors is True


@pytest.mark.parametrize(
    "extra_args, expected_errors, expected_bad_rows",
    (
        ({"allow_international_letters": False}, True, {0}),
        ({"allow_international_letters": True}, False, set()),
    ),
)
def test_accepts_international_addresses_when_allowed(extra_args, expected_errors, expected_bad_rows):
    recipients = RecipientCSV(
        """
            address line 1, address line 2, address line 3
            First Lastname, 123 Example St, Fiji
            First Lastname, 234 Example St, 2552 HN Den Haag, Netherlands
        """,
        template=_sample_template("letter"),
        **extra_args,
    )
    rows_with_errors_index = _index_rows(recipients.rows_with_bad_recipients)
    assert recipients.has_errors is expected_errors
    assert rows_with_errors_index == expected_bad_rows
    # Prove that the error isn’t because the given country is unknown
    assert recipients[0].as_postal_address.country == Country("Fiji")


def test_address_validation_speed():
    # We should be able to validate 1000 lines of address data in about
    # a second – if it starts to get slow, something is inefficient
    number_of_lines = 1000

    nl_addresses_with_valid_postcodes = "\n".join(
        "{name}, {street}, {postcode} {city}".format(
            name="Example name",
            street=f"{randrange(1, 1000)} Example Street",
            postcode=f"{randrange(1000, 9999)} {choice('BCDFGHJKLMNPQRSTVWXYZ')}{choice('BCDFGHJKLMNPQRSTVWXYZ')}",
            city=choice(["Amsterdam", "Utrecht", "Den Haag", "Rotterdam"]),
        )
        for _ in range(number_of_lines)
    )

    recipients = RecipientCSV(
        "address line 1, address line 2, address line 3\n" + nl_addresses_with_valid_postcodes,
        template=_sample_template("letter"),
        allow_international_letters=True,
    )

    for row in recipients:
        assert not row.has_bad_postal_address


def test_errors_on_qr_codes_with_too_much_data():
    template = _sample_template("letter", content="QR: ((qr_code))")
    template.is_message_empty = Mock(return_value=False)

    short = "a" * 504
    long = "a" * 505
    recipients = RecipientCSV(
        f"""
            address_line_1, address_line_2, address_line_3, qr_code
            First Lastname, 123 Example St, 1234 AA Den Haag, {short}
            First Lastname, 123 Example St, 1234 AA Den Haag,{long}
        """,
        template=template,
    )
    assert recipients.has_errors is True
    assert len(list(recipients.rows_with_errors)) == 1
    assert recipients.rows_as_list[0].has_error is False
    assert recipients.rows_as_list[0].qr_code_too_long is None
    assert recipients.rows_as_list[1].has_error is True
    assert isinstance(recipients.rows_as_list[1].qr_code_too_long, QrCodeTooLong)


@pytest.mark.parametrize(
    "content",
    [
        "hello",
        "hello ((name))",
    ],
)
@pytest.mark.parametrize(
    "file_contents,template_type",
    [
        pytest.param("", "sms", marks=pytest.mark.xfail),
        pytest.param("name", "sms", marks=pytest.mark.xfail),
        pytest.param("e-mailadres", "sms", marks=pytest.mark.xfail),
        pytest.param(
            "address_line_1",
            "letter",
            marks=pytest.mark.xfail,
        ),
        pytest.param(
            "address_line_1, address_line_2",
            "letter",
            marks=pytest.mark.xfail,
        ),
        pytest.param(
            "address_line_6, postcode",
            "letter",
            marks=pytest.mark.xfail,
        ),
        pytest.param(
            "address_line_1, postcode, address_line_6",
            "letter",
            marks=pytest.mark.xfail,
        ),
        ("telefoonnummer", "sms"),
        ("telefoonnummer,name", "sms"),
        ("e-mailadres", "email"),
        ("e-mailadres,name", "email"),
        ("TELEFOONNUMMER", "sms"),
        ("e-mailadres", "email"),
        ("address_line_1, address_line_2, postcode", "letter"),
        ("address_line_1, address_line_2, address_line_6", "letter"),
        ("address_line_1, address_line_2, address_line_3", "letter"),
        ("address_line_4, address_line_5, address_line_6", "letter"),
        (
            "address_line_1, address_line_2, address_line_3, address_line_4, address_line_5, address_line_6, postcode",
            "letter",
        ),
    ],
)
def test_recipient_column(content, file_contents, template_type):
    assert RecipientCSV(file_contents, template=_sample_template(template_type, content)).has_recipient_columns


@pytest.mark.parametrize(
    "template_type, expected",
    (
        ("email", ["e-mailadres"]),
        ("sms", ["telefoonnummer"]),
        (
            "letter",
            [
                "address line 1",
                "address line 2",
                "address line 3",
                "address line 4",
                "address line 5",
                "postcode",
                "address line 6",
            ],
        ),
    ),
)
def test_recipient_column_headers(template_type, expected):
    recipients = RecipientCSV("", template=_sample_template(template_type))
    assert (recipients.recipient_column_headers) == (first_column_headings[template_type]) == (expected)
