import itertools
import string
import unicodedata
from functools import partial
from random import choice, randrange
from unittest.mock import Mock

import pytest
from ordered_set import OrderedSet

from notifications_utils import SMS_CHAR_COUNT_LIMIT
from notifications_utils.countries import Country
from notifications_utils.qr_code import QrCodeTooLong
from notifications_utils.recipients import (
    Cell,
    RecipientCSV,
    Row,
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
    "template_type, expected",
    (
        ("email", ["email address"]),
        ("sms", ["phone number"]),
        (
            "letter",
            [
                "address line 1",
                "address line 2",
                "address line 3",
                "address line 4",
                "address line 5",
                "address line 6",
                "postcode",
                "address line 7",
            ],
        ),
    ),
)
def test_recipient_column_headers(template_type, expected):
    recipients = RecipientCSV("", template=_sample_template(template_type))
    assert (recipients.recipient_column_headers) == (first_column_headings[template_type]) == (expected)


@pytest.mark.parametrize(
    "file_contents,template_type,expected",
    [
        (
            "",
            "sms",
            [],
        ),
        (
            "phone number",
            "sms",
            [],
        ),
        (
            """
                phone number,name
                +44 123, test1
                +44 456,test2
            """,
            "sms",
            [[("phone number", "+44 123"), ("name", "test1")], [("phone number", "+44 456"), ("name", "test2")]],
        ),
        (
            """
                phone number,name
                +44 123,
                +44 456
            """,
            "sms",
            [[("phone number", "+44 123"), ("name", None)], [("phone number", "+44 456"), ("name", None)]],
        ),
        (
            """
                email address,name
                test@example.com,test1
                test2@example.com, test2
            """,
            "email",
            [
                [("email address", "test@example.com"), ("name", "test1")],
                [("email address", "test2@example.com"), ("name", "test2")],
            ],
        ),
        (
            """
                email address
                test@example.com,test1,red
                test2@example.com, test2,blue
            """,
            "email",
            [
                [("email address", "test@example.com"), (None, ["test1", "red"])],
                [("email address", "test2@example.com"), (None, ["test2", "blue"])],
            ],
        ),
        (
            """
                email address,name
                test@example.com,"test1"
                test2@example.com,"   test2    "
                test3@example.com," test3"
            """,
            "email",
            [
                [("email address", "test@example.com"), ("name", "test1")],
                [("email address", "test2@example.com"), ("name", "test2")],
                [("email address", "test3@example.com"), ("name", "test3")],
            ],
        ),
        (
            """
                email address,date,name
                test@example.com,"Nov 28, 2016",test1
                test2@example.com,"Nov 29, 2016",test2
            """,
            "email",
            [
                [("email address", "test@example.com"), ("date", "Nov 28, 2016"), ("name", "test1")],
                [("email address", "test2@example.com"), ("date", "Nov 29, 2016"), ("name", "test2")],
            ],
        ),
        (
            """
                address_line_1
                Alice
                Bob
            """,
            "letter",
            [[("address_line_1", "Alice")], [("address_line_1", "Bob")]],
        ),
        (
            """
                address line 1,address line 2,address line 5,address line 6,postcode,name,thing
                A. Name,,,,XM4 5HQ,example,example
            """,
            "letter",
            [
                [
                    ("addressline1", "A. Name"),
                    ("addressline2", None),
                    # optional address rows 3 and 4 not in file
                    ("addressline5", None),
                    ("addressline5", None),
                    ("postcode", "XM4 5HQ"),
                    ("name", "example"),
                    ("thing", "example"),
                ]
            ],
        ),
        (
            """
                phone number, list, list, list
                07900900001, cat, rat, gnat
                07900900002, dog, hog, frog
                07900900003, elephant
            """,
            "sms",
            [
                [("phone number", "07900900001"), ("list", ["cat", "rat", "gnat"])],
                [("phone number", "07900900002"), ("list", ["dog", "hog", "frog"])],
                [("phone number", "07900900003"), ("list", ["elephant", None, None])],
            ],
        ),
    ],
)
def test_get_rows(file_contents, template_type, expected):
    rows = list(RecipientCSV(file_contents, template=_sample_template(template_type)).rows)
    if not expected:
        assert rows == expected
    for index, row in enumerate(expected):
        assert len(rows[index].items()) == len(row)
        for key, value in row:
            assert rows[index].get(key).data == value


def test_get_rows_does_no_error_checking_of_rows_or_cells(mocker):
    has_error_mock = mocker.patch.object(Row, "has_error")
    has_bad_recipient_mock = mocker.patch.object(Row, "has_bad_recipient")
    has_missing_data_mock = mocker.patch.object(Row, "has_missing_data")
    cell_recipient_error_mock = mocker.patch.object(Cell, "recipient_error")

    recipients = RecipientCSV(
        """
            email address, name
            a@b.com,
            a@b.com, My Name
            a@b.com,


        """,
        template=_sample_template("email", "hello ((name))"),
        max_errors_shown=3,
    )

    rows = recipients.get_rows()
    for _ in range(3):
        assert next(rows).recipient == "a@b.com"

    assert has_error_mock.called is False
    assert has_bad_recipient_mock.called is False
    assert has_missing_data_mock.called is False
    assert cell_recipient_error_mock.called is False


def test_get_rows_only_iterates_over_file_once(mocker):
    row_mock = mocker.patch("notifications_utils.recipients.Row")

    recipients = RecipientCSV(
        """
            email address, name
            a@b.com,
            a@b.com, My Name
            a@b.com,


        """,
        template=_sample_template("email", "hello ((name))"),
    )

    rows = recipients.get_rows()
    for _ in range(3):
        next(rows)

    assert row_mock.call_count == 3
    assert recipients.rows_as_list is None


@pytest.mark.parametrize(
    "file_contents,template_type,expected",
    [
        (
            """
                phone number,name
                07700900460, test1
                +447700 900 460,test2
                ,
            """,
            "sms",
            [
                {"index": 0, "message_too_long": False},
                {"index": 1, "message_too_long": False},
            ],
        ),
        (
            """
                email address,name,colour
                test@example.com,test1,blue
                test2@example.com, test2,red
            """,
            "email",
            [
                {"index": 0, "message_too_long": False},
                {"index": 1, "message_too_long": False},
            ],
        ),
    ],
)
def test_get_annotated_rows(file_contents, template_type, expected):
    recipients = RecipientCSV(
        file_contents, template=_sample_template(template_type, "hello ((name))"), max_initial_rows_shown=1
    )
    for index, expected_row in enumerate(expected):
        annotated_row = list(recipients.rows)[index]
        assert annotated_row.index == expected_row["index"]
        assert annotated_row.message_too_long == expected_row["message_too_long"]
    assert len(list(recipients.rows)) == 2
    assert len(list(recipients.initial_rows)) == 1
    assert not recipients.has_errors


def test_get_rows_with_errors():
    recipients = RecipientCSV(
        """
            email address, name
            a@b.com,
            a@b.com,
            a@b.com,
            a@b.com,
            a@b.com,
            a@b.com,


        """,
        template=_sample_template("email", "hello ((name))"),
        max_errors_shown=3,
    )
    assert len(list(recipients.rows_with_errors)) == 6
    assert len(list(recipients.initial_rows_with_errors)) == 3
    assert recipients.has_errors


@pytest.mark.parametrize(
    "template_type, row_count, header, filler, row_with_error",
    [
        ("email", 500, "email address\n", "test@example.com\n", "test at example dot com"),
        ("sms", 500, "phone number\n", "07900900123\n", "12345"),
    ],
)
def test_big_list_validates_right_through(template_type, row_count, header, filler, row_with_error):
    big_csv = RecipientCSV(
        header + (filler * (row_count - 1) + row_with_error),
        template=_sample_template(template_type),
        max_errors_shown=100,
        max_initial_rows_shown=3,
    )
    assert len(list(big_csv.rows)) == row_count
    assert _index_rows(big_csv.rows_with_bad_recipients) == {row_count - 1}  # 0 indexed
    assert _index_rows(big_csv.rows_with_errors) == {row_count - 1}
    assert len(list(big_csv.initial_rows_with_errors)) == 1
    assert big_csv.has_errors


@pytest.mark.parametrize(
    "template_type, row_count, header, filler",
    [
        ("email", 50, "email address\n", "test@example.com\n"),
        ("sms", 50, "phone number\n", "07900900123\n"),
    ],
)
def test_check_if_message_too_long_for_sms_but_not_email_in_CSV(mocker, template_type, row_count, header, filler):
    # we do not validate email size for CSVs to avoid performance issues
    RecipientCSV(
        header + filler * row_count,
        template=_sample_template(template_type),
        max_errors_shown=100,
        max_initial_rows_shown=3,
    )
    is_message_too_long = mocker.patch("notifications_utils.template.Template.is_message_too_long", side_effect=False)
    if template_type == "email":
        is_message_too_long.assert_not_called  # noqa
    else:
        is_message_too_long.called  # noqa


def test_overly_big_list_stops_processing_rows_beyond_max(mocker):
    mock_strip_and_remove_obscure_whitespace = mocker.patch(
        "notifications_utils.recipients.strip_and_remove_obscure_whitespace",
        side_effect=lambda value: {"07700900123": "07700900123", "example": "example"}.get(value),
    )
    mock_insert_or_append_to_dict = mocker.patch(
        "notifications_utils.recipients.insert_or_append_to_dict",
    )

    big_csv = RecipientCSV(
        "phonenumber,name\n" + ("07700900123,example\n" * 123),
        template=_sample_template("sms", content="hello ((name))"),
    )
    big_csv.max_rows = 10

    # Our CSV has lots of rows…
    assert big_csv.too_many_rows
    assert len(big_csv) == 123

    # …but we’ve only called the expensive whitespace function on each
    # of the 2 cells in the first 10 rows
    assert len(mock_strip_and_remove_obscure_whitespace.call_args_list) == 20

    # …and we’ve only called the function which builds the internal data
    # structure once for each of the first 10 rows
    assert len(mock_insert_or_append_to_dict.call_args_list) == 10


def test_file_with_lots_of_empty_columns():
    process = Mock()

    lots_of_commas = "," * 10_000

    for row in RecipientCSV(
        f"phone_number{lots_of_commas}\n" + (f"07900900900{lots_of_commas}\n" * 100),
        template=_sample_template("sms"),
    ):
        assert [(key, cell.data) for key, cell in row.items()] == [
            # Note that we haven’t stored any of the empty cells
            ("phonenumber", "07900900900")
        ]
        process()

    assert process.call_count == 100


def test_empty_column_names():
    recipient_csv = RecipientCSV(
        """
            phone_number,,,name
            07900900123,foo,bar,baz
        """,
        template=_sample_template("sms"),
    )

    assert recipient_csv[0]["phone_number"].data == "07900900123"
    assert recipient_csv[0][""].data == ["foo", "bar"]
    assert recipient_csv[0]["name"].data == "baz"


@pytest.mark.parametrize(
    "file_contents,template,expected_recipients,expected_personalisation",
    [
        (
            """
                phone number,name, date
                +44 123,test1,today
                +44456,    ,tomorrow
                ,,
                , ,
            """,
            _sample_template("sms", "hello ((name))"),
            ["+44 123", "+44456"],
            [{"name": "test1"}, {"name": None}],
        ),
        (
            """
                email address,name,colour
                test@example.com,test1,red
                testatexampledotcom,test2,blue
            """,
            _sample_template("email", "((colour))"),
            ["test@example.com", "testatexampledotcom"],
            [{"colour": "red"}, {"colour": "blue"}],
        ),
        (
            """
                email address
                test@example.com,test1,red
                testatexampledotcom,test2,blue
            """,
            _sample_template("email"),
            ["test@example.com", "testatexampledotcom"],
            [],
        ),
    ],
)
def test_get_recipient(file_contents, template, expected_recipients, expected_personalisation):
    recipients = RecipientCSV(file_contents, template=template)

    for index, row in enumerate(expected_personalisation):
        for key, value in row.items():
            assert recipients[index].recipient == expected_recipients[index]
            assert recipients[index].personalisation.get(key) == value


@pytest.mark.parametrize(
    "file_contents,template,expected_recipients,expected_personalisation",
    [
        (
            """
                email address,test
                test@example.com,test1,red
                testatexampledotcom,test2,blue
            """,
            _sample_template("email", "((test))"),
            [(0, "test@example.com"), (1, "testatexampledotcom")],
            [
                {"emailaddress": "test@example.com", "test": "test1"},
                {"emailaddress": "testatexampledotcom", "test": "test2"},
            ],
        )
    ],
)
def test_get_recipient_respects_order(file_contents, template, expected_recipients, expected_personalisation):
    recipients = RecipientCSV(file_contents, template=template)

    for row, email in expected_recipients:
        assert (
            recipients[row].index,
            recipients[row].recipient,
            recipients[row].personalisation,
        ) == (
            row,
            email,
            expected_personalisation[row],
        )


@pytest.mark.parametrize(
    "file_contents,template_type,expected,expected_missing",
    [
        ("", "sms", [], {"phone number", "name"}),
        (
            """
                phone number,name
                07700900460,test1
                07700900460,test1
                07700900460,test1
            """,
            "sms",
            ["phone number", "name"],
            set(),
        ),
        (
            """
                email address,name,colour
            """,
            "email",
            ["email address", "name", "colour"],
            set(),
        ),
        (
            """
                address_line_1, address_line_2, postcode, name
            """,
            "letter",
            ["address_line_1", "address_line_2", "postcode", "name"],
            set(),
        ),
        (
            """
                email address,colour
            """,
            "email",
            ["email address", "colour"],
            {"name"},
        ),
        (
            """
                address_line_1, address_line_2, name
            """,
            "letter",
            ["address_line_1", "address_line_2", "name"],
            set(),
        ),
        (
            """
                phone number,list,list,name,list
            """,
            "sms",
            ["phone number", "list", "name"],
            set(),
        ),
    ],
)
def test_column_headers(file_contents, template_type, expected, expected_missing):
    recipients = RecipientCSV(file_contents, template=_sample_template(template_type, "((name))"))
    assert recipients.column_headers == expected
    assert recipients.missing_column_headers == expected_missing
    assert recipients.has_errors == bool(expected_missing)


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
        pytest.param("email address", "sms", marks=pytest.mark.xfail),
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
            "address_line_1, postcode, address_line_7",
            "letter",
            marks=pytest.mark.xfail,
        ),
        ("phone number", "sms"),
        ("phone number,name", "sms"),
        ("email address", "email"),
        ("email address,name", "email"),
        ("PHONENUMBER", "sms"),
        ("email_address", "email"),
        ("address_line_1, address_line_2, postcode", "letter"),
        ("address_line_1, address_line_2, address_line_7", "letter"),
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
    "file_contents,template_type,rows_with_bad_recipients,rows_with_missing_data",
    [
        (
            """
                phone number,name,date
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
                phone number,name
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
            # missing postcode
            """
                address_line_1,address_line_2,address_line_3,address_line_4,address_line_5,postcode,date
                name,          building,      street,        town,          county,        SE1 7LS,today
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
                name,           SE1 7LS, today
            """,
            "letter",
            {0},
            set(),
        ),
        (
            # optional address fields not filled in
            """
                address_line_1,address_line_2,address_line_3,address_line_4,address_line_5,postcode,date
                name          ,123 fake st.  ,              ,              ,              ,SE1 7LS,today
                name          ,              ,              ,              ,              ,SE1 7LS,today
            """,
            "letter",
            {1},
            set(),
        ),
        (
            # Can use any address columns
            """
                address_line_3, address_line_4, address_line_7, date
                name          , 123 fake st.,   SE1 7LS,        today
            """,
            "letter",
            set(),
            set(),
        ),
        (
            """
                ,,,,,,,,,Phone number
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
        partial(RecipientCSV, allow_international_sms=False),
    ],
)
def test_bad_or_missing_data(
    file_contents, template_type, rows_with_bad_recipients, rows_with_missing_data, partial_instance
):
    recipients = partial_instance(file_contents, template=_sample_template(template_type, "((date))"))
    assert _index_rows(recipients.rows_with_bad_recipients) == rows_with_bad_recipients
    assert _index_rows(recipients.rows_with_missing_data) == rows_with_missing_data
    if rows_with_bad_recipients or rows_with_missing_data:
        assert recipients.has_errors is True


@pytest.mark.parametrize(
    "file_contents,rows_with_bad_recipients,expectected_count",
    [
        (
            """
            phone number
            800000000000
            1234
            +447900123
        """,
            {0, 1, 2},
            0,
        ),
        (
            """
            phone number, country
            1-202-555-0104, USA
            +12025550104, USA
            +2304031000, Mauritius
        """,
            set(),
            3,
        ),
    ],
)
def test_international_recipients(file_contents, rows_with_bad_recipients, expectected_count):
    recipients = RecipientCSV(
        file_contents,
        template=_sample_template("sms"),
        allow_international_sms=True,
    )
    assert recipients.international_sms_count == expectected_count
    assert _index_rows(recipients.rows_with_bad_recipients) == rows_with_bad_recipients


@pytest.mark.parametrize(
    "extra_args, too_many",
    (
        ({"remaining_international_sms_messages": 2}, True),
        ({"remaining_international_sms_messages": 3}, False),
        ({}, False),
    ),
)
def test_international_sms_limit(extra_args, too_many):
    recipients = RecipientCSV(
        """
        phone number, count international
        +12025550104, 1
        +447900900123, (UK)
        +12025550104, 2
        +12025550104, 3
        07900 900 321, (UK with no country code)
        +447797292290, Jersey (doesn’t count towards international limit)
        """,
        template=_sample_template("sms"),
        allow_international_sms=True,
        **extra_args,
    )
    assert recipients.more_international_sms_than_can_send is too_many
    assert recipients.has_errors is too_many


@pytest.mark.parametrize("allow_international", [True, False])
@pytest.mark.parametrize("remaining_international_sms_messages", [1, 0, -1])
def test_international_sms_limit_doesnt_apply_for_email(allow_international, remaining_international_sms_messages):
    recipients = RecipientCSV(
        """
        email_address,
        example@gmail.com
        """,
        template=_sample_template("email"),
        allow_international_sms=allow_international,
        remaining_international_sms_messages=remaining_international_sms_messages,
    )
    assert recipients.more_international_sms_than_can_send is False
    assert recipients.has_errors is False


@pytest.mark.parametrize("allow_international_sms", (True, False))
def test_international_sms_limit_handles_negative_limit(allow_international_sms):
    recipients = RecipientCSV(
        """
        phone number
        +447900900123
        """,
        template=_sample_template("sms"),
        allow_international_sms=allow_international_sms,
        remaining_international_sms_messages=-1,
    )
    assert not recipients.more_international_sms_than_can_send
    assert not recipients.has_errors


def test_international_sms_limit_is_ok_with_uk_number_if_no_international_remaining():
    recipients = RecipientCSV(
        """
        phone_number,
        07790 000 123
        """,
        template=_sample_template("sms"),
        allow_international_sms=True,
        remaining_international_sms_messages=0,
    )
    assert recipients.more_international_sms_than_can_send is False
    assert recipients.has_errors is False


@pytest.mark.parametrize(
    "file_contents,rows_with_bad_recipients",
    [
        (
            """
            phone number
            800000000000
            1234
            +447900123
        """,
            {0, 1, 2},
        ),
        (
            """
            phone number
            +441709510122
            020 3002 4300
            44117 925 1001

        """,
            set(),
        ),
    ],
)
def test_sms_to_uk_landlines(file_contents, rows_with_bad_recipients):
    recipients = RecipientCSV(
        file_contents,
        template=_sample_template("sms"),
        allow_sms_to_uk_landline=True,
    )
    assert _index_rows(recipients.rows_with_bad_recipients) == rows_with_bad_recipients


def test_errors_when_too_many_rows():
    recipients = RecipientCSV(
        "email address\n" + ("a@b.com\n" * 101),
        template=_sample_template("email"),
    )

    # Confirm the normal max_row limit
    assert recipients.max_rows == 100_000
    # Override to make this test faster
    recipients.max_rows = 100

    assert recipients.too_many_rows is True
    assert recipients.has_errors is True
    assert recipients.rows[99]["email_address"].data == "a@b.com"
    # We stop processing subsequent rows
    assert recipients.rows[100] is None


@pytest.mark.parametrize(
    "file_contents,template_type,guestlist,count_of_rows_with_errors",
    [
        (
            """
                phone number
                07700900460
                07700900461
                07700900462
                07700900463
            """,
            "sms",
            ["+447700900460"],  # Same as first phone number but in different format
            3,
        ),
        (
            """
                phone number
                7700900460
                447700900461
                07700900462
            """,
            "sms",
            ["07700900460", "07700900461", "07700900462", "07700900463", "test@example.com"],
            0,
        ),
        (
            """
                email address
                IN_GUESTLIST@EXAMPLE.COM
                not_in_guestlist@example.com
            """,
            "email",
            ["in_guestlist@example.com", "07700900460"],  # Email case differs to the one in the CSV
            1,
        ),
    ],
)
def test_recipient_guestlist(file_contents, template_type, guestlist, count_of_rows_with_errors):
    recipients = RecipientCSV(file_contents, template=_sample_template(template_type), guestlist=guestlist)

    if count_of_rows_with_errors:
        assert not recipients.allowed_to_send_to
    else:
        assert recipients.allowed_to_send_to

    # Make sure the guestlist isn’t emptied by reading it. If it’s an iterator then
    # there’s a risk that it gets emptied after being read once
    recipients.guestlist = (str(fake_number) for fake_number in range(7700900888, 7700900898))
    list(recipients.guestlist)
    assert not recipients.allowed_to_send_to
    assert recipients.has_errors

    # An empty guestlist is treated as no guestlist at all
    recipients.guestlist = []
    assert recipients.allowed_to_send_to
    recipients.guestlist = itertools.chain()
    assert recipients.allowed_to_send_to


def test_detects_rows_which_result_in_overly_long_messages():
    template = SMSMessageTemplate(
        {"content": "((placeholder))", "template_type": "sms"},
        sender=None,
        prefix=None,
    )
    recipients = RecipientCSV(
        """
            phone number,placeholder
            07700900460,1
            07700900461,{one_under}
            07700900462,{exactly}
            07700900463,{one_over}
        """.format(
            one_under="a" * (SMS_CHAR_COUNT_LIMIT - 1),
            exactly="a" * SMS_CHAR_COUNT_LIMIT,
            one_over="a" * (SMS_CHAR_COUNT_LIMIT + 1),
        ),
        template=template,
    )
    assert _index_rows(recipients.rows_with_errors) == {3}
    assert _index_rows(recipients.rows_with_message_too_long) == {3}
    assert recipients.has_errors
    assert recipients[0].has_error_spanning_multiple_cells is False
    assert recipients[1].has_error_spanning_multiple_cells is False
    assert recipients[2].has_error_spanning_multiple_cells is False
    assert recipients[3].has_error_spanning_multiple_cells is True


def test_denys_invalid_numbers_when_should_validate_phone_number_set_to_true():
    template = SMSMessageTemplate(
        {"content": "test", "template_type": "sms"},
        sender=None,
        prefix=None,
    )
    recipients = RecipientCSV(
        """
            phone number
            077009004605425890423582904
            07700900461432482390483204
            077009004622342342340239489023
            07700900463523423423432432
        """,
        template=template,
        should_validate_phone_number=True,
    )
    assert recipients.has_errors
    assert _index_rows(recipients.rows_with_errors) == {0, 1, 2, 3}


def test_allows_invalid_numbers_when_should_validate_phone_number_set_to_false():
    template = SMSMessageTemplate(
        {"content": "test", "template_type": "sms"},
        sender=None,
        prefix=None,
    )
    recipients = RecipientCSV(
        """
            phone number
            077009004605425890423582904
            07700900461432482390483204
            077009004622342342340239489023
            07700900463523423423432432
        """,
        template=template,
        should_validate_phone_number=False,
    )
    assert not recipients.has_errors
    assert dict(_index_rows(recipients.rows_with_errors)) == {}


def test_detects_rows_which_result_in_empty_messages():
    template = SMSMessageTemplate(
        {"content": "((show??content))", "template_type": "sms"},
        sender=None,
        prefix=None,
    )
    recipients = RecipientCSV(
        """
            phone number,show
            07700900460,yes
            07700900462,no
            07700900463,yes
        """,
        template=template,
    )
    assert _index_rows(recipients.rows_with_errors) == {1}
    assert _index_rows(recipients.rows_with_empty_message) == {1}
    assert recipients.has_errors
    assert recipients[0].has_error_spanning_multiple_cells is False
    assert recipients[1].has_error_spanning_multiple_cells is True
    assert recipients[2].has_error_spanning_multiple_cells is False


@pytest.mark.parametrize(
    "key, expected",
    sum(
        [
            [(key, expected) for key in group]
            for expected, group in [
                ("07700900460", ("phone number", "   PHONENUMBER", "phone_number", "phone-number", "phoneNumber")),
                ("Jo", ("FIRSTNAME", "first name", "first_name ", "first-name", "firstName")),
                ("Bloggs", ("Last    Name", "LASTNAME", "    last_name", "last-name", "lastName   ")),
            ]
        ],
        [],
    ),
)
def test_ignores_spaces_and_case_in_placeholders(key, expected):
    recipients = RecipientCSV(
        """
            phone number,FIRSTNAME, Last Name
            07700900460, Jo, Bloggs
        """,
        template=_sample_template("sms", content="((phone_number)) ((First Name)) ((lastname))"),
    )
    first_row = recipients[0]
    assert first_row.get(key).data == expected
    assert first_row[key].data == expected
    assert first_row.recipient == "07700900460"
    assert len(first_row.items()) == 3
    assert not recipients.has_errors

    assert recipients.missing_column_headers == set()
    recipients.placeholders = {"one", "TWO", "Thirty_Three"}
    assert recipients.missing_column_headers == {"one", "TWO", "Thirty_Three"}
    assert recipients.has_errors


@pytest.mark.parametrize(
    "character, name",
    (
        (" ", "SPACE"),
        # these ones don’t have unicode names
        ("\n", None),  # newline
        ("\r", None),  # carriage return
        ("\t", None),  # tab
        ("\u180e", "MONGOLIAN VOWEL SEPARATOR"),
        ("\u200b", "ZERO WIDTH SPACE"),
        ("\u200c", "ZERO WIDTH NON-JOINER"),
        ("\u200d", "ZERO WIDTH JOINER"),
        ("\u2060", "WORD JOINER"),
        ("\ufeff", "ZERO WIDTH NO-BREAK SPACE"),
        # all the things
        (" \n\r\t\u000a\u000d\u180e\u200b\u200c\u200d\u2060\ufeff", None),
    ),
)
def test_ignores_leading_whitespace_in_file(character, name):
    if name is not None:
        assert unicodedata.name(character) == name

    recipients = RecipientCSV(
        f"{character}emailaddress\ntest@example.com",
        template=_sample_template("email"),
    )
    first_row = recipients[0]

    assert recipients.column_headers == ["emailaddress"]
    assert recipients.recipient_column_headers == ["email address"]
    assert recipients.missing_column_headers == set()
    assert recipients.placeholders == ["email address"]

    assert first_row.get("email address").data == "test@example.com"
    assert first_row["email address"].data == "test@example.com"
    assert first_row.recipient == "test@example.com"

    assert not recipients.has_errors


def test_error_if_too_many_recipients():
    recipients = RecipientCSV(
        "phone number,\n07700900460,\n07700900460,\n07700900460,",
        template=_sample_template("sms"),
        remaining_messages=2,
    )
    assert recipients.has_errors
    assert recipients.more_rows_than_can_send


def test_dont_error_if_too_many_recipients_not_specified():
    recipients = RecipientCSV(
        "phone number,\n07700900460,\n07700900460,\n07700900460,",
        template=_sample_template("sms"),
    )
    assert not recipients.has_errors
    assert not recipients.more_rows_than_can_send


@pytest.mark.parametrize(
    "index, expected_row",
    [
        (
            0,
            {
                "phone number": "07700 90000 1",
                "colour": "red",
            },
        ),
        (
            1,
            {
                "phone_number": "07700 90000 2",
                "COLOUR": "green",
            },
        ),
        (
            2,
            {"p h o n e  n u m b e r": "07700 90000 3", "   colour   ": "blue"},
        ),
        pytest.param(
            3,
            {"phone number": "foo"},
            marks=pytest.mark.xfail(raises=IndexError),
        ),
        (
            -1,
            {"p h o n e  n u m b e r": "07700 90000 3", "   colour   ": "blue"},
        ),
    ],
)
def test_recipients_can_be_accessed_by_index(index, expected_row):
    recipients = RecipientCSV(
        """
            phone number, colour
            07700 90000 1, red
            07700 90000 2, green
            07700 90000 3, blue
        """,
        template=_sample_template("sms"),
    )
    for key, value in expected_row.items():
        assert recipients[index][key].data == value


@pytest.mark.parametrize("international_sms", (True, False))
def test_multiple_sms_recipient_columns(international_sms):
    recipients = RecipientCSV(
        """
            phone number, phone number, phone_number, foo
            07900 900111, 07900 900222, 07900 900333, bar
        """,
        template=_sample_template("sms"),
        allow_international_sms=international_sms,
    )
    assert recipients.column_headers == ["phone number", "phone_number", "foo"]
    assert recipients.column_headers_as_column_keys == {"phonenumber": "", "foo": ""}.keys()
    assert recipients.rows[0].get("phone number").data == ("07900 900333")
    assert recipients.rows[0].get("phone_number").data == ("07900 900333")
    assert recipients.rows[0].get("phone number").error is None
    assert recipients.duplicate_recipient_column_headers == OrderedSet(["phone number", "phone_number"])
    assert recipients.has_errors


@pytest.mark.parametrize(
    "column_name", ("phone_number", "phonenumber", "phone number", "phone-number", "p h o n e  n u m b e r")
)
def test_multiple_sms_recipient_columns_with_missing_data(column_name):
    recipients = RecipientCSV(
        f"""
            names, phone number, {column_name}
            "Joanna and Steve", 07900 900111
        """,
        template=_sample_template("sms"),
        allow_international_sms=True,
    )
    expected_column_headers = ["names", "phone number"]
    if column_name != "phone number":
        expected_column_headers.append(column_name)
    assert recipients.column_headers == expected_column_headers
    assert recipients.column_headers_as_column_keys == {"phonenumber": "", "names": ""}.keys()
    # A piece of weirdness uncovered: since rows are created before spaces in column names are normalised, when
    # there are duplicate recipient columns and there is data for only one of the columns, if the columns have the same
    # spacing, phone number data will be a list of this one phone number and None, while if the spacing style differs
    # between two duplicate column names, the phone number data will be None. If there are no duplicate columns
    # then our code finds the phone number well regardless of the spacing, so this should not affect our users.
    phone_number_data = None
    if column_name == "phone number":
        phone_number_data = ["07900 900111", None]
    assert recipients.rows[0]["phonenumber"].data == phone_number_data
    assert recipients.rows[0].get("phone number").error is None
    expected_duplicated_columns = ["phone number"]
    if column_name != "phone number":
        expected_duplicated_columns.append(column_name)
    assert recipients.duplicate_recipient_column_headers == OrderedSet(expected_duplicated_columns)
    assert recipients.has_errors


def test_multiple_email_recipient_columns():
    recipients = RecipientCSV(
        """
            EMAILADDRESS, email_address, foo
            one@two.com,  two@three.com, bar
        """,
        template=_sample_template("email"),
    )
    assert recipients.rows[0].get("email address").data == ("two@three.com")
    assert recipients.rows[0].get("email address").error is None
    assert recipients.has_errors
    assert recipients.duplicate_recipient_column_headers == OrderedSet(["EMAILADDRESS", "email_address"])
    assert recipients.has_errors


def test_multiple_letter_recipient_columns():
    recipients = RecipientCSV(
        """
            address line 1, Address Line 2, address line 1, address_line_2
            1,2,3,4
        """,
        template=_sample_template("letter"),
    )
    assert recipients.rows[0].get("addressline1").data == ("3")
    assert recipients.rows[0].get("addressline1").error is None
    assert recipients.has_errors
    assert recipients.duplicate_recipient_column_headers == OrderedSet(
        ["address line 1", "Address Line 2", "address line 1", "address_line_2"]
    )
    assert recipients.has_errors


def test_displayed_rows_when_some_rows_have_errors():
    recipients = RecipientCSV(
        """
            email address, name
            a@b.com,
            a@b.com,
            a@b.com, My Name
            a@b.com,
            a@b.com,
        """,
        template=_sample_template("email", "((name))"),
        max_errors_shown=3,
    )

    assert len(list(recipients.displayed_rows)) == 3


def test_displayed_rows_when_there_are_no_rows_with_errors():
    recipients = RecipientCSV(
        """
            email address, name
            a@b.com, My Name
            a@b.com, My Name
            a@b.com, My Name
            a@b.com, My Name
        """,
        template=_sample_template("email", "((name))"),
        max_errors_shown=3,
    )

    assert len(list(recipients.displayed_rows)) == 4


def test_multi_line_placeholders_work():
    recipients = RecipientCSV(
        """
            email address, data
            a@b.com, "a\nb\n\nc"
        """,
        template=_sample_template("email", "((data))"),
    )

    assert recipients.rows[0].personalisation["data"] == "a\nb\n\nc"


@pytest.mark.parametrize(
    "extra_args, expected_errors, expected_bad_rows",
    (
        ({}, True, {0}),
        ({"allow_international_letters": False}, True, {0}),
        ({"allow_international_letters": True}, False, set()),
    ),
)
def test_accepts_international_addresses_when_allowed(extra_args, expected_errors, expected_bad_rows):
    recipients = RecipientCSV(
        """
            address line 1, address line 2, address line 3
            First Lastname, 123 Example St, Fiji
            First Lastname, 123 Example St, SW1A 1AA
        """,
        template=_sample_template("letter"),
        **extra_args,
    )
    assert recipients.has_errors is expected_errors
    assert _index_rows(recipients.rows_with_bad_recipients) == expected_bad_rows
    # Prove that the error isn’t because the given country is unknown
    assert recipients[0].as_postal_address.country == Country("Fiji")


def test_address_validation_speed():
    # We should be able to validate 1000 lines of address data in about
    # a second – if it starts to get slow, something is inefficient
    number_of_lines = 1000
    uk_addresses_with_valid_postcodes = "\n".join(
        "{n} Example Street, London, {a}{b} {c}{d}{e}".format(
            n=randrange(1000),
            a=choice(["n", "e", "sw", "se", "w"]),
            b=choice(range(1, 10)),
            c=choice(range(1, 10)),
            d=choice("ABDefgHJLNPqrstUWxyZ"),
            e=choice("ABDefgHJLNPqrstUWxyZ"),
        )
        for i in range(number_of_lines)
    )
    recipients = RecipientCSV(
        "address line 1, address line 2, address line 3\n" + (uk_addresses_with_valid_postcodes),
        template=_sample_template("letter"),
        allow_international_letters=False,
    )
    for row in recipients:
        assert not row.has_bad_postal_address


def test_email_validation_speed():
    email_addresses = "\n".join(
        f"{choice(string.ascii_letters)}{choice(string.ascii_letters)}@example-{randrange(1000)}.com,Example,Thursday"
        for i in range(1000)
    )
    recipients = RecipientCSV(
        "email address,name,day\n" + email_addresses,
        template=_sample_template(
            "email",
            content=f"""
                hello ((name)) today is ((day))
                here’s the letter ‘a’ 1000 times:
                {"a" * 1000}
            """,
        ),
    )
    for row in recipients:
        assert not row.has_error


@pytest.mark.parametrize("should_validate", [True, False])
def test_recipient_csv_checks_should_validate_flag(should_validate):
    template = _sample_template("sms")
    template.is_message_empty = Mock(return_value=False)

    recipients = RecipientCSV(
        """phone number,name
        07700900460, test1
        +447700 900 460,test2""",
        template=template,
        should_validate=should_validate,
    )

    recipients._get_error_for_field = Mock(return_value=None)

    list(recipients.get_rows())

    assert template.is_message_empty.called is should_validate
    assert recipients._get_error_for_field.called is should_validate


def test_errors_on_qr_codes_with_too_much_data():
    template = _sample_template("letter", content="QR: ((qr_code))")
    template.is_message_empty = Mock(return_value=False)

    short = "a" * 504
    long = "a" * 505
    recipients = RecipientCSV(
        f"""
            address_line_1, address_line_2, address_line_3, qr_code
            First Lastname, 123 Example St, SW1A 1AA,{short}
            First Lastname, 123 Example St, SW1A 1AA,{long}
        """,
        template=template,
    )

    assert recipients.has_errors is True
    assert len(list(recipients.rows_with_errors)) == 1
    assert recipients.rows_as_list[0].has_error is False
    assert recipients.rows_as_list[0].qr_code_too_long is None
    assert recipients.rows_as_list[1].has_error is True
    assert isinstance(recipients.rows_as_list[1].qr_code_too_long, QrCodeTooLong)
