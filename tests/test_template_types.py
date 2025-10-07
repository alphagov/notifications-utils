import datetime
import os
from time import process_time
from unittest import mock

import pytest
from bs4 import BeautifulSoup
from freezegun import freeze_time
from markupsafe import Markup
from ordered_set import OrderedSet

from notifications_utils.formatters import unlink_govuk_escaped
from notifications_utils.template import (
    BaseEmailTemplate,
    BaseLetterTemplate,
    BaseSMSTemplate,
    HTMLEmailTemplate,
    LetterPreviewTemplate,
    LetterPrintTemplate,
    PlainTextEmailTemplate,
    SMSBodyPreviewTemplate,
    SMSMessageTemplate,
    SMSPreviewTemplate,
    SubjectMixin,
    Template,
)


@pytest.mark.parametrize(
    "template_class",
    (
        Template,
        BaseEmailTemplate,
        BaseLetterTemplate,
        BaseSMSTemplate,
    ),
)
def test_abstract_classes_cant_be_instantiated(template_class):
    with pytest.raises(TypeError) as error:
        template_class({})
    assert f"Can't instantiate abstract class {template_class.__name__}" in str(error.value)
    assert "__str__" in str(error.value)


@pytest.mark.parametrize(
    "template_class, expected_error",
    (
        (HTMLEmailTemplate, ("Cannot initialise HTMLEmailTemplate with sms template_type")),
        (LetterPreviewTemplate, ("Cannot initialise LetterPreviewTemplate with sms template_type")),
    ),
)
def test_errors_for_incompatible_template_type(template_class, expected_error):
    with pytest.raises(TypeError) as error:
        template_class({"content": "", "subject": "", "template_type": "sms"})
    assert str(error.value) == expected_error


def test_html_email_inserts_body():
    assert "the &lt;em&gt;quick&lt;/em&gt; brown fox" in str(
        HTMLEmailTemplate({"content": "the <em>quick</em> brown fox", "subject": "", "template_type": "email"})
    )


@pytest.mark.parametrize("content", ("DOCTYPE", "html", "body", "GOV.UK", "hello world"))
def test_default_template(content):
    assert content in str(
        HTMLEmailTemplate(
            {
                "content": "hello world",
                "subject": "",
                "template_type": "email",
            }
        )
    )


@pytest.mark.parametrize("show_banner", (True, False))
def test_govuk_banner(show_banner):
    email = HTMLEmailTemplate(
        {
            "content": "hello world",
            "subject": "",
            "template_type": "email",
        }
    )
    email.govuk_banner = show_banner
    if show_banner:
        assert "GOV.UK" in str(email)
    else:
        assert "GOV.UK" not in str(email)


def test_brand_banner_shows():
    email = str(
        HTMLEmailTemplate(
            {"content": "hello world", "subject": "", "template_type": "email"}, brand_banner=True, govuk_banner=False
        )
    )
    assert ('<td width="10" height="10" valign="middle"></td>') not in email
    assert (
        'role="presentation" width="100%" style="border-collapse: collapse;min-width: 100%;width: 100% !important;"'
    ) in email


@pytest.mark.parametrize(
    "brand_logo, brand_text, brand_colour",
    [
        ("http://example.com/image.png", "Example", "red"),
        ("http://example.com/image.png", "Example", "#f00"),
        ("http://example.com/image.png", "Example", None),
        ("http://example.com/image.png", "", "#f00"),
        (None, "Example", "#f00"),
    ],
)
def test_brand_data_shows(brand_logo, brand_text, brand_colour):
    email = str(
        HTMLEmailTemplate(
            {"content": "hello world", "subject": "", "template_type": "email"},
            brand_banner=True,
            govuk_banner=False,
            brand_logo=brand_logo,
            brand_text=brand_text,
            brand_colour=brand_colour,
        )
    )

    assert "GOV.UK" not in email
    if brand_logo:
        assert brand_logo in email
    if brand_text:
        assert brand_text in email
    if brand_colour:
        assert f'bgcolor="{brand_colour}"' in email


def test_alt_text_with_brand_text_and_govuk_banner_shown():
    email = str(
        HTMLEmailTemplate(
            {"content": "hello world", "subject": "", "template_type": "email"},
            govuk_banner=True,
            brand_logo="http://example.com/image.png",
            brand_text="Example",
            brand_banner=True,
            brand_alt_text="Notify Logo",
        )
    )
    assert 'alt=""' in email
    assert 'alt="Notify Logo"' not in email


def test_alt_text_with_no_brand_text_and_govuk_banner_shown():
    email = str(
        HTMLEmailTemplate(
            {"content": "hello world", "subject": "", "template_type": "email"},
            govuk_banner=True,
            brand_logo="http://example.com/image.png",
            brand_text=None,
            brand_banner=True,
            brand_alt_text="Notify Logo",
        )
    )
    assert 'alt=""' in email
    assert 'alt="Notify Logo"' in email


@pytest.mark.parametrize(
    "brand_banner, brand_text, expected_alt_text",
    [
        (True, None, 'alt="Notify Logo"'),
        (True, "Example", 'alt=""'),
        (False, "Example", 'alt=""'),
        (False, None, 'alt="Notify Logo"'),
    ],
)
def test_alt_text_with_no_govuk_banner(brand_banner, brand_text, expected_alt_text):
    email = str(
        HTMLEmailTemplate(
            {"content": "hello world", "subject": "", "template_type": "email"},
            govuk_banner=False,
            brand_logo="http://example.com/image.png",
            brand_text=brand_text,
            brand_banner=brand_banner,
            brand_alt_text="Notify Logo",
        )
    )

    assert expected_alt_text in email


@pytest.mark.parametrize("complete_html", (True, False))
@pytest.mark.parametrize(
    "branding_should_be_present, brand_logo, brand_text, brand_colour",
    [
        (True, "http://example.com/image.png", "Example", "#f00"),
        (True, "http://example.com/image.png", "Example", None),
        (True, "http://example.com/image.png", "", None),
        (False, None, "Example", "#f00"),
        (False, "http://example.com/image.png", None, "#f00"),
    ],
)
@pytest.mark.parametrize("content", ("DOCTYPE", "html", "body"))
def test_complete_html(complete_html, branding_should_be_present, brand_logo, brand_text, brand_colour, content):
    email = str(
        HTMLEmailTemplate(
            {"content": "hello world", "subject": "", "template_type": "email"},
            complete_html=complete_html,
            brand_logo=brand_logo,
            brand_text=brand_text,
            brand_colour=brand_colour,
        )
    )

    if complete_html:
        assert content in email
    else:
        assert content not in email

    if branding_should_be_present:
        assert brand_logo in email
        assert brand_text in email

        if brand_colour:
            assert brand_colour in email
            assert "##" not in email


def test_subject_is_page_title():
    email = BeautifulSoup(
        str(
            HTMLEmailTemplate(
                {"content": "", "subject": "this is the subject", "template_type": "email"},
            )
        ),
        features="html.parser",
    )
    assert email.select_one("title").text == "this is the subject"


def test_preheader_is_at_start_of_html_emails():
    assert (
        '<body style="font-family: Helvetica, Arial, sans-serif;font-size: 16px;margin: 0;color:#0b0c0c;">\n'
        "\n"
        '<span style="display: none;font-size: 1px;color: #fff; max-height: 0;" hidden>content…</span>'
    ) in str(HTMLEmailTemplate({"content": "content", "subject": "subject", "template_type": "email"}))


@pytest.mark.parametrize(
    "content, values, expected_preheader",
    [
        (
            (
                "Hello (( name ))\n"
                "\n"
                '# This - is a "heading"\n'
                "\n"
                "My favourite websites' URLs are:\n"
                "- GOV.UK\n"
                "- https://www.example.com\n"
            ),
            {"name": "Jo"},
            "Hello Jo This – is a “heading” My favourite websites’ URLs are: • GOV.​UK • https://www.example.com",
        ),
        (
            ("[Markdown link](https://www.example.com)\n"),
            {},
            "Markdown link",
        ),
        (
            """
            Lorem Ipsum is simply dummy text of the printing and
            typesetting industry.

            Lorem Ipsum has been the industry’s standard dummy text
            ever since the 1500s, when an unknown printer took a galley
            of type and scrambled it to make a type specimen book.

            Lorem Ipsum is simply dummy text of the printing and
            typesetting industry.

            Lorem Ipsum has been the industry’s standard dummy text
            ever since the 1500s, when an unknown printer took a galley
            of type and scrambled it to make a type specimen book.
        """,
            {},
            (
                "Lorem Ipsum is simply dummy text of the printing and "
                "typesetting industry. Lorem Ipsum has been the industry’s "
                "standard dummy text ever since the 1500s, when an unknown "
                "printer took a galley of type and scrambled it to make a "
                "type specimen book. Lorem Ipsu"
            ),
        ),
        (
            "short email",
            {},
            "short email",
        ),
    ],
)
@mock.patch("notifications_utils.template.HTMLEmailTemplate.jinja_template.render", return_value="mocked")
def test_content_of_preheader_in_html_emails(
    mock_jinja_template,
    content,
    values,
    expected_preheader,
):
    assert (
        str(HTMLEmailTemplate({"content": content, "subject": "subject", "template_type": "email"}, values)) == "mocked"
    )
    assert mock_jinja_template.call_args[0][0]["preheader"] == expected_preheader


@pytest.mark.parametrize(
    "template_class, template_type, extra_args, result, markdown_renderer",
    [
        [
            HTMLEmailTemplate,
            "email",
            {},
            ("the quick brown fox\n\njumped over the lazy dog\n"),
            "notifications_utils.template.notify_email_markdown",
        ],
        [
            LetterPreviewTemplate,
            "letter",
            {},
            ("the quick brown fox\n\njumped over the lazy dog\n"),
            "notifications_utils.template.notify_letter_preview_markdown",
        ],
    ],
)
def test_markdown_in_templates(
    template_class,
    template_type,
    extra_args,
    result,
    markdown_renderer,
):
    with mock.patch(markdown_renderer, return_value="") as mock_markdown_renderer:
        str(
            template_class(
                {
                    "content": ("the quick ((colour)) ((animal))\n\njumped over the lazy dog"),
                    "subject": "animal story",
                    "template_type": template_type,
                },
                {"animal": "fox", "colour": "brown"},
                **extra_args,
            )
        )
    mock_markdown_renderer.assert_called_once_with(result)


@pytest.mark.parametrize(
    "template_class, template_type, extra_attributes",
    [
        (HTMLEmailTemplate, "email", 'style="word-wrap: break-word; color: #1D70B8;"'),
        (SMSPreviewTemplate, "sms", 'class="govuk-link govuk-link--no-visited-state"'),
        pytest.param(SMSBodyPreviewTemplate, "sms", 'style="word-wrap: break-word;', marks=pytest.mark.xfail),
    ],
)
@pytest.mark.parametrize(
    "url, url_with_entities_replaced",
    [
        ("http://example.com", "http://example.com"),
        ("http://www.gov.uk/", "http://www.gov.uk/"),
        ("https://www.gov.uk/", "https://www.gov.uk/"),
        ("http://service.gov.uk", "http://service.gov.uk"),
        (
            "http://service.gov.uk/blah.ext?q=a%20b%20c&order=desc#fragment",
            "http://service.gov.uk/blah.ext?q=a%20b%20c&amp;order=desc#fragment",
        ),
        pytest.param("example.com", "example.com", marks=pytest.mark.xfail),
        pytest.param("www.example.com", "www.example.com", marks=pytest.mark.xfail),
        pytest.param(
            "http://service.gov.uk/blah.ext?q=one two three",
            "http://service.gov.uk/blah.ext?q=one two three",
            marks=pytest.mark.xfail,
        ),
        pytest.param("ftp://example.com", "ftp://example.com", marks=pytest.mark.xfail),
        pytest.param("mailto:test@example.com", "mailto:test@example.com", marks=pytest.mark.xfail),
    ],
)
def test_makes_links_out_of_URLs(extra_attributes, template_class, template_type, url, url_with_entities_replaced):
    assert f'<a {extra_attributes} href="{url_with_entities_replaced}">{url_with_entities_replaced}</a>' in str(
        template_class({"content": url, "subject": "", "template_type": template_type})
    )


@pytest.mark.parametrize(
    "url, url_with_entities_replaced",
    (
        ("example.com", "example.com"),
        ("www.gov.uk/", "www.gov.uk/"),
        ("service.gov.uk", "service.gov.uk"),
        ("gov.uk/coronavirus", "gov.uk/coronavirus"),
        (
            "service.gov.uk/blah.ext?q=a%20b%20c&order=desc#fragment",
            "service.gov.uk/blah.ext?q=a%20b%20c&amp;order=desc#fragment",
        ),
    ),
)
def test_makes_links_out_of_URLs_without_protocol_in_sms_and(
    url,
    url_with_entities_replaced,
):
    assert (
        f"<a "
        f'class="govuk-link govuk-link--no-visited-state" '
        f'href="http://{url_with_entities_replaced}">'
        f"{url_with_entities_replaced}"
        f"</a>"
    ) in str(SMSPreviewTemplate({"content": url, "subject": "", "template_type": "sms"}))


@pytest.mark.parametrize(
    "content, html_snippet",
    (
        (
            (
                "You’ve been invited to a service. Click this link:\n"
                "https://service.example.com/accept_invite/a1b2c3d4\n"
                "\n"
                "Thanks\n"
            ),
            (
                '<a style="word-wrap: break-word; color: #1D70B8;"'
                ' href="https://service.example.com/accept_invite/a1b2c3d4">'
                "https://service.example.com/accept_invite/a1b2c3d4"
                "</a>"
            ),
        ),
        (
            ("https://service.example.com/accept_invite/?a=b&c=d&"),
            (
                '<a style="word-wrap: break-word; color: #1D70B8;"'
                ' href="https://service.example.com/accept_invite/?a=b&amp;c=d&amp;">'
                "https://service.example.com/accept_invite/?a=b&amp;c=d&amp;"
                "</a>"
            ),
        ),
    ),
)
def test_HTML_template_has_URLs_replaced_with_links(content, html_snippet):
    assert html_snippet in str(HTMLEmailTemplate({"content": content, "subject": "", "template_type": "email"}))


@pytest.mark.parametrize(
    "template_content,expected",
    [
        ("gov.uk", "gov.\u200buk"),
        ("GOV.UK", "GOV.\u200bUK"),
        ("Gov.uk", "Gov.\u200buk"),
        ("https://gov.uk", "https://gov.uk"),
        ("https://www.gov.uk", "https://www.gov.uk"),
        ("www.gov.uk", "www.gov.uk"),
        ("gov.uk/register-to-vote", "gov.uk/register-to-vote"),
        ("gov.uk?q=", "gov.uk?q="),
    ],
)
def test_escaping_govuk_in_email_templates(template_content, expected):
    assert unlink_govuk_escaped(template_content) == expected
    assert expected in str(
        PlainTextEmailTemplate(
            {
                "content": template_content,
                "subject": "",
                "template_type": "email",
            }
        )
    )
    assert expected in str(
        HTMLEmailTemplate(
            {
                "content": template_content,
                "subject": "",
                "template_type": "email",
            }
        )
    )


@pytest.mark.parametrize(
    "template_content",
    (
        "line one\u2028line two",
        "line one\u3164line two",
    ),
)
@pytest.mark.parametrize("template_class", (PlainTextEmailTemplate, HTMLEmailTemplate))
def test_stripping_of_unsupported_characters_in_email_templates(template_content, template_class):
    assert "line oneline two" in str(
        template_class(
            {
                "content": template_content,
                "subject": "",
                "template_type": "email",
            }
        )
    )


@mock.patch("notifications_utils.template.add_prefix", return_value="")
@pytest.mark.parametrize(
    "template_class, prefix, body, expected_call",
    [
        (SMSMessageTemplate, "a", "b", (Markup("b"), "a")),
        (SMSPreviewTemplate, "a", "b", (Markup("b"), "a")),
        (SMSMessageTemplate, None, "b", (Markup("b"), None)),
        (SMSPreviewTemplate, None, "b", (Markup("b"), None)),
        (SMSMessageTemplate, "<em>ht&ml</em>", "b", (Markup("b"), "<em>ht&ml</em>")),
        (SMSPreviewTemplate, "<em>ht&ml</em>", "b", (Markup("b"), "&lt;em&gt;ht&amp;ml&lt;/em&gt;")),
    ],
)
def test_sms_message_adds_prefix(add_prefix, template_class, prefix, body, expected_call):
    template = template_class({"content": body, "template_type": template_class.template_type})
    template.prefix = prefix
    template.sender = None
    str(template)
    add_prefix.assert_called_once_with(*expected_call)


@mock.patch("notifications_utils.template.add_prefix", return_value="")
@pytest.mark.parametrize(
    "template_class",
    [
        SMSMessageTemplate,
        SMSPreviewTemplate,
    ],
)
@pytest.mark.parametrize(
    "show_prefix, prefix, body, sender, expected_call",
    [
        (False, "a", "b", "c", (Markup("b"), None)),
        (True, "a", "b", None, (Markup("b"), "a")),
        (True, "a", "b", False, (Markup("b"), "a")),
    ],
)
def test_sms_message_adds_prefix_only_if_asked_to(
    add_prefix,
    show_prefix,
    prefix,
    body,
    sender,
    expected_call,
    template_class,
):
    template = template_class(
        {"content": body, "template_type": template_class.template_type},
        prefix=prefix,
        show_prefix=show_prefix,
        sender=sender,
    )
    str(template)
    add_prefix.assert_called_once_with(*expected_call)


@pytest.mark.parametrize("content_to_look_for", ["GOVUK", "sms-message-sender"])
@pytest.mark.parametrize(
    "show_sender",
    [
        True,
        pytest.param(False, marks=pytest.mark.xfail),
    ],
)
def test_sms_message_preview_shows_sender(
    show_sender,
    content_to_look_for,
):
    assert content_to_look_for in str(
        SMSPreviewTemplate(
            {"content": "foo", "template_type": "sms"},
            sender="GOVUK",
            show_sender=show_sender,
        )
    )


def test_sms_message_preview_hides_sender_by_default():
    assert SMSPreviewTemplate({"content": "foo", "template_type": "sms"}).show_sender is False


@mock.patch("notifications_utils.template.sms_encode", return_value="downgraded")
@pytest.mark.parametrize(
    "template_class, extra_args, expected_call",
    (
        (SMSMessageTemplate, {"prefix": "Service name"}, "Service name: Message"),
        (SMSPreviewTemplate, {"prefix": "Service name"}, "Service name: Message"),
        (SMSBodyPreviewTemplate, {}, "Message"),
    ),
)
def test_sms_messages_downgrade_non_sms(
    mock_sms_encode,
    template_class,
    extra_args,
    expected_call,
):
    template = str(template_class({"content": "Message", "template_type": "sms"}, **extra_args))
    assert "downgraded" in str(template)
    mock_sms_encode.assert_called_once_with(expected_call)


@mock.patch("notifications_utils.template.sms_encode", return_value="downgraded")
def test_sms_messages_dont_downgrade_non_sms_if_setting_is_false(mock_sms_encode):
    template = str(
        SMSPreviewTemplate(
            {"content": "😎", "template_type": "sms"},
            prefix="👉",
            downgrade_non_sms_characters=False,
        )
    )
    assert "👉: 😎" in str(template)
    assert mock_sms_encode.called is False


@mock.patch("notifications_utils.template.nl2br")
def test_sms_preview_adds_newlines(nl2br):
    content = "the\nquick\n\nbrown fox"
    str(SMSPreviewTemplate({"content": content, "template_type": "sms"}))
    nl2br.assert_called_once_with(content)


@pytest.mark.parametrize(
    "content",
    [
        ("one newline\ntwo newlines\n\nend"),  # Unix-style
        ("one newline\r\ntwo newlines\r\n\r\nend"),  # Windows-style
        ("one newline\rtwo newlines\r\rend"),  # Mac Classic style
        ("\t\t\n\r one newline\ntwo newlines\r\r\nend\n\n  \r \n \t "),  # A mess
    ],
)
def test_sms_message_normalises_newlines(content):
    assert repr(str(SMSMessageTemplate({"content": content, "template_type": "sms"}))) == repr(
        "one newline\ntwo newlines\n\nend"
    )


@pytest.mark.parametrize(
    "template_class",
    (
        SMSMessageTemplate,
        SMSBodyPreviewTemplate,
        # Note: SMSPreviewTemplate not tested here as both will render full
        # HTML template, not just the body
    ),
)
def test_phone_templates_normalise_whitespace(template_class):
    content = "  Hi\u00a0there\u00a0 what's\u200d up\t"
    assert (
        str(template_class({"content": content, "template_type": template_class.template_type})) == "Hi there what's up"
    )


@freeze_time("2012-12-12 12:12:12")
@mock.patch("notifications_utils.template.LetterPreviewTemplate.jinja_template.render")
@mock.patch("notifications_utils.template.unlink_govuk_escaped")
@mock.patch("notifications_utils.template.notify_letter_preview_markdown", return_value="Bar")
@pytest.mark.parametrize(
    "values, expected_address",
    [
        (
            {},
            [
                "<span class='placeholder-no-brackets'>address line 1</span>",
                "<span class='placeholder-no-brackets'>address line 2</span>",
                "<span class='placeholder-no-brackets'>address line 3</span>",
                "<span class='placeholder-no-brackets'>address line 4</span>",
                "<span class='placeholder-no-brackets'>address line 5</span>",
                "<span class='placeholder-no-brackets'>address line 6</span>",
                "<span class='placeholder-no-brackets'>address line 7</span>",
            ],
        ),
        (
            {
                "address line 1": "123 Fake Street",
                "address line 6": "United Kingdom",
            },
            [
                "123 Fake Street",
                "<span class='placeholder-no-brackets'>address line 2</span>",
                "<span class='placeholder-no-brackets'>address line 3</span>",
                "<span class='placeholder-no-brackets'>address line 4</span>",
                "<span class='placeholder-no-brackets'>address line 5</span>",
                "United Kingdom",
                "<span class='placeholder-no-brackets'>address line 7</span>",
            ],
        ),
        (
            {
                "address line 1": "123 Fake Street",
                "address line 2": "City of Town",
                "postcode": "SW1A 1AA",
            },
            [
                "123 Fake Street",
                "City of Town",
                "SW1A 1AA",
            ],
        ),
    ],
)
@pytest.mark.parametrize(
    "contact_block, expected_rendered_contact_block",
    [
        (None, ""),
        ("", ""),
        (
            """
            The Pension Service
            Mail Handling Site A
            Wolverhampton  WV9 1LU

            Telephone: 0845 300 0168
            Email: fpc.customercare@dwp.gsi.gov.uk
            Monday - Friday  8am - 6pm
            www.gov.uk
        """,
            (
                "The Pension Service<br>"
                "Mail Handling Site A<br>"
                "Wolverhampton  WV9 1LU<br>"
                "<br>"
                "Telephone: 0845 300 0168<br>"
                "Email: fpc.customercare@dwp.gsi.gov.uk<br>"
                "Monday - Friday  8am - 6pm<br>"
                "www.gov.uk"
            ),
        ),
    ],
)
@pytest.mark.parametrize(
    "extra_args, expected_logo_file_name, expected_logo_class",
    [
        ({}, None, None),
        ({"logo_file_name": "example.foo"}, "example.foo", "foo"),
    ],
)
@pytest.mark.parametrize(
    "additional_extra_args, expected_date",
    [
        ({}, "12 December 2012"),
        ({"date": None}, "12 December 2012"),
        ({"date": datetime.date.fromtimestamp(0)}, "1 January 1970"),
    ],
)
def test_letter_preview_renderer(
    letter_markdown,
    unlink_govuk,
    jinja_template,
    values,
    expected_address,
    contact_block,
    expected_rendered_contact_block,
    extra_args,
    expected_logo_file_name,
    expected_logo_class,
    additional_extra_args,
    expected_date,
):
    extra_args.update(additional_extra_args)
    str(
        LetterPreviewTemplate(
            {"content": "Foo", "subject": "Subject", "template_type": "letter"},
            values,
            contact_block=contact_block,
            **extra_args,
        )
    )
    jinja_template.assert_called_once_with(
        {
            "address": expected_address,
            "subject": "Subject",
            "message": "Bar",
            "date": expected_date,
            "contact_block": expected_rendered_contact_block,
            "admin_base_url": "http://localhost:6012",
            "logo_file_name": expected_logo_file_name,
            "logo_class": expected_logo_class,
            "language": "english",
            "includes_first_page": True,
        }
    )
    letter_markdown.assert_called_once_with(Markup("Foo\n"))
    unlink_govuk.assert_not_called()


@freeze_time("2001-01-01 12:00:00.000000")
@mock.patch("notifications_utils.template.LetterPreviewTemplate.jinja_template.render")
def test_letter_preview_renderer_without_mocks(jinja_template):
    str(
        LetterPreviewTemplate(
            {"content": "Foo", "subject": "Subject", "template_type": "letter"},
            {"addressline1": "name", "addressline2": "street", "postcode": "SW1 1AA"},
            contact_block="",
        )
    )

    jinja_template_locals = jinja_template.call_args_list[0][0][0]

    assert jinja_template_locals["address"] == [
        "name",
        "street",
        "SW1 1AA",
    ]
    assert jinja_template_locals["subject"] == "Subject"
    assert jinja_template_locals["message"] == "<p>Foo</p>"
    assert jinja_template_locals["date"] == "1 January 2001"
    assert jinja_template_locals["contact_block"] == ""
    assert jinja_template_locals["admin_base_url"] == "http://localhost:6012"
    assert jinja_template_locals["logo_file_name"] is None


@mock.patch("notifications_utils.template.LetterPreviewTemplate.jinja_template.render")
def test_letter_preview_renders_QR_code_correctly(jinja_template):
    str(
        LetterPreviewTemplate(
            {
                "content": "This is your link:\n\nqr: https://www.example.com",
                "subject": "Subject",
                "template_type": "letter",
            },
            {"addressline1": "name", "addressline2": "street", "postcode": "SW1 1AA"},
            contact_block="",
        )
    )

    jinja_template_locals = jinja_template.call_args_list[0][0][0]

    expected_qr_code_svg = '<p>This is your link:</p><p><div class=\'qrcode\'><svg viewBox="0 0 25 25"><path stroke="#000" d="M0 0.5h7m1 0h2m1 0h1m2 0h1m3 0h7m-25 1h1m5 0h1m1 0h6m4 0h1m5 0h1m-25 1h1m1 0h3m1 0h1m1 0h1m2 0h1m1 0h1m1 0h2m1 0h1m1 0h3m1 0h1m-25 1h1m1 0h3m1 0h1m2 0h2m2 0h1m4 0h1m1 0h3m1 0h1m-25 1h1m1 0h3m1 0h1m1 0h1m5 0h1m1 0h1m1 0h1m1 0h3m1 0h1m-25 1h1m5 0h1m3 0h2m2 0h1m3 0h1m5 0h1m-25 1h7m1 0h1m1 0h1m1 0h1m1 0h1m1 0h1m1 0h7m-16 1h1m2 0h2m2 0h1m-17 1h1m2 0h6m1 0h2m4 0h2m2 0h1m1 0h3m-24 1h3m3 0h2m2 0h5m1 0h1m1 0h5m-24 1h1m3 0h1m1 0h3m2 0h1m1 0h1m1 0h2m1 0h2m1 0h1m2 0h1m-25 1h1m2 0h1m5 0h2m1 0h1m3 0h1m2 0h1m1 0h4m-24 1h1m3 0h2m1 0h1m1 0h1m4 0h2m1 0h1m5 0h1m-25 1h2m1 0h2m2 0h1m4 0h6m2 0h1m2 0h1m-24 1h3m2 0h3m2 0h1m4 0h4m1 0h5m-25 1h1m1 0h2m3 0h2m3 0h1m3 0h2m1 0h1m1 0h2m1 0h1m-25 1h1m5 0h1m1 0h2m1 0h3m2 0h5m1 0h2m-16 1h1m1 0h2m1 0h1m1 0h2m3 0h1m1 0h2m-24 1h7m1 0h3m1 0h1m3 0h1m1 0h1m1 0h1m3 0h1m-25 1h1m5 0h1m1 0h4m1 0h1m1 0h2m3 0h1m2 0h1m-24 1h1m1 0h3m1 0h1m1 0h1m2 0h2m1 0h7m2 0h2m-25 1h1m1 0h3m1 0h1m1 0h2m2 0h5m1 0h1m4 0h2m-25 1h1m1 0h3m1 0h1m4 0h2m4 0h1m2 0h5m-25 1h1m5 0h1m2 0h1m1 0h2m1 0h1m4 0h2m1 0h3m-25 1h7m1 0h1m1 0h5m1 0h2m3 0h1m2 0h1"/></svg></div></p>'  # noqa
    assert jinja_template_locals["message"] == expected_qr_code_svg


@pytest.mark.parametrize(
    "template_class",
    (
        BaseLetterTemplate,
        LetterPreviewTemplate,
        LetterPrintTemplate,
    ),
)
def test_max_page_count_on_all_types_of_letter_template(template_class):
    assert template_class.max_page_count == 10
    assert template_class.max_sheet_count == 5


@pytest.mark.parametrize(
    "template_class",
    (
        LetterPreviewTemplate,
        LetterPrintTemplate,
    ),
)
def test_too_many_pages_raises_for_unknown_page_count(template_class):
    template = template_class({"content": "Content", "subject": "Subject", "template_type": "letter"})
    with pytest.raises(AttributeError):
        template.too_many_pages  # noqa


@freeze_time("2023-10-31 00:00:01")
def test_letter_template_shows_date_and_page_count_in_welsh_if_language_set_to_welsh():
    template = BeautifulSoup(
        str(
            LetterPreviewTemplate(
                {
                    "content": "Some content",
                    "subject": "Some subject",
                    "letter_welsh_content": "Welsh content",
                    "letter_welsh_subject": "Welsh subject",
                    "template_type": "letter",
                },
                language="welsh",
            )
        ),
        features="html.parser",
    )

    assert "31 Hydref 2023" in template.text

    assert 'content: "Tudalen " counter(page) " o " counter(pages);' in template.select_one("style").text


def test_letter_template_shows_welsh_subject_and_content_if_language_set_to_welsh():
    template = LetterPreviewTemplate(
        {
            "content": "Very good",
            "letter_welsh_content": "Yn gwych",
            "subject": "How are you",
            "letter_welsh_subject": "Sut dych chi",
            "template_type": "letter",
        },
        language="welsh",
    )

    assert template.subject == "Sut dych chi"
    assert template.content == "Yn gwych"


def test_letter_template_detects_all_placeholders_in_both_english_and_welsh_subject_and_content():
    template = LetterPreviewTemplate(
        {
            "content": "Send us ((document_type))",
            "letter_welsh_content": "Anfonwch ((document_type_cy)) atom",
            "subject": "Getting ((allowance_type))",
            "letter_welsh_subject": "Cael ((allowance_type_cy))",
            "template_type": "letter",
        }
    )

    assert template.placeholders == OrderedSet(
        ["allowance_type_cy", "allowance_type", "document_type_cy", "document_type"]
    )


@pytest.mark.parametrize(
    "template_class",
    (
        SMSBodyPreviewTemplate,
        SMSMessageTemplate,
        SMSPreviewTemplate,
    ),
)
@pytest.mark.parametrize(
    "template_json",
    (
        {"content": ""},
        {"content": "", "subject": "subject"},
    ),
)
def test_sms_templates_have_no_subject(template_class, template_json):
    template_json.update(template_type="sms")
    assert not hasattr(
        template_class(template_json),
        "subject",
    )


def test_subject_line_gets_applied_to_correct_template_types():
    for cls in [
        HTMLEmailTemplate,
        PlainTextEmailTemplate,
        LetterPreviewTemplate,
    ]:
        assert issubclass(cls, SubjectMixin)
    for cls in [
        SMSBodyPreviewTemplate,
        SMSMessageTemplate,
        SMSPreviewTemplate,
    ]:
        assert not issubclass(cls, SubjectMixin)


@pytest.mark.parametrize(
    "template_class, template_type, extra_args",
    (
        (HTMLEmailTemplate, "email", {}),
        (PlainTextEmailTemplate, "email", {}),
        (LetterPreviewTemplate, "letter", {}),
        (LetterPrintTemplate, "letter", {}),
    ),
)
def test_subject_line_gets_replaced(template_class, template_type, extra_args):
    template = template_class({"content": "", "template_type": template_type, "subject": "((name))"}, **extra_args)
    assert template.subject == Markup("<span class='placeholder'>&#40;&#40;name&#41;&#41;</span>")
    template.values = {"name": "Jo"}
    assert template.subject == "Jo"


@pytest.mark.parametrize(
    "template_class, template_type, extra_args",
    (
        (HTMLEmailTemplate, "email", {}),
        (PlainTextEmailTemplate, "email", {}),
        (LetterPreviewTemplate, "letter", {}),
        (LetterPrintTemplate, "letter", {}),
    ),
)
@pytest.mark.parametrize(
    "content, values, expected_count",
    [
        ("Content with ((placeholder))", {"placeholder": "something extra"}, 28),
        ("Content with ((placeholder))", {"placeholder": ""}, 12),
        ("Just content", {}, 12),
        ("((placeholder))  ", {"placeholder": "  "}, 0),
        ("  ", {}, 0),
    ],
)
def test_character_count_for_non_sms_templates(
    template_class,
    template_type,
    extra_args,
    content,
    values,
    expected_count,
):
    template = template_class(
        {
            "content": content,
            "subject": "Hi",
            "template_type": template_type,
        },
        **extra_args,
    )
    template.values = values
    assert template.content_count == expected_count


@pytest.mark.parametrize(
    "template_class",
    [
        SMSMessageTemplate,
        SMSPreviewTemplate,
    ],
)
@pytest.mark.parametrize(
    "content, values, prefix, expected_count_in_template, expected_count_in_notification",
    [
        # is an unsupported unicode character so should be replaced with a ?
        ("深", {}, None, 1, 1),
        # is a supported unicode character so should be kept as is
        ("Ŵ", {}, None, 1, 1),
        ("'First line.\n", {}, None, 12, 12),
        ("\t\n\r", {}, None, 0, 0),
        ("Content with ((placeholder))", {"placeholder": "something extra here"}, None, 13, 33),
        ("Content with ((placeholder))", {"placeholder": ""}, None, 13, 12),
        ("Just content", {}, None, 12, 12),
        ("((placeholder))  ", {"placeholder": "  "}, None, 0, 0),
        ("  ", {}, None, 0, 0),
        ("Content with ((placeholder))", {"placeholder": "something extra here"}, "GDS", 18, 38),
        ("Just content", {}, "GDS", 17, 17),
        ("((placeholder))  ", {"placeholder": "  "}, "GDS", 5, 4),
        ("  ", {}, "GDS", 4, 4),  # Becomes `GDS:`
        ("  G      D       S  ", {}, None, 5, 5),  # Becomes `G D S`
        ("P1 \n\n\n\n\n\n P2", {}, None, 6, 6),  # Becomes `P1\n\nP2`
        ("a    ((placeholder))    b", {"placeholder": ""}, None, 4, 3),  # Counted as `a  b` then `a b`
    ],
)
def test_character_count_for_sms_templates(
    content, values, prefix, expected_count_in_template, expected_count_in_notification, template_class
):
    template = template_class(
        {"content": content, "template_type": "sms"},
        prefix=prefix,
    )
    template.sender = None
    assert template.content_count == expected_count_in_template
    template.values = values
    assert template.content_count == expected_count_in_notification


@pytest.mark.parametrize(
    "msg, expected_sms_fragment_count",
    [
        ("à" * 71, 1),  # welsh character in GSM
        ("à" * 160, 1),
        ("à" * 161, 2),
        ("à" * 306, 2),
        ("à" * 307, 3),
        ("à" * 612, 4),
        ("à" * 613, 5),
        ("à" * 765, 5),
        ("à" * 766, 6),
        ("à" * 918, 6),
        ("à" * 919, 7),
        ("ÿ" * 70, 1),  # welsh character not in GSM, so send as unicode
        ("ÿ" * 71, 2),
        ("ÿ" * 134, 2),
        ("ÿ" * 135, 3),
        ("ÿ" * 268, 4),
        ("ÿ" * 269, 5),
        ("ÿ" * 402, 6),
        ("ÿ" * 403, 7),
        ("à" * 70 + "ÿ", 2),  # just one non-gsm character means it's sent at unicode
        ("🚀" * 160, 1),  # non-welsh unicode characters are downgraded to gsm, so are only one fragment long
    ],
)
def test_sms_fragment_count_accounts_for_unicode_and_welsh_characters(
    msg,
    expected_sms_fragment_count,
):
    template = SMSMessageTemplate({"content": msg, "template_type": "sms"})
    assert template.fragment_count == expected_sms_fragment_count


@pytest.mark.parametrize(
    "msg, expected_sms_fragment_count",
    [
        # all extended GSM characters
        ("^" * 81, 2),
        # GSM characters plus extended GSM
        ("a" * 158 + "|", 1),
        ("a" * 159 + "|", 2),
        ("a" * 304 + "[", 2),
        ("a" * 304 + "[]", 3),
        # Welsh character plus extended GSM
        ("â" * 132 + "{", 2),
        ("â" * 133 + "}", 3),
    ],
)
def test_sms_fragment_count_accounts_for_extended_gsm_characters(
    msg,
    expected_sms_fragment_count,
):
    template = SMSMessageTemplate({"content": msg, "template_type": "sms"})
    assert template.fragment_count == expected_sms_fragment_count


@pytest.mark.parametrize(
    "template_class",
    [
        SMSMessageTemplate,
        SMSPreviewTemplate,
    ],
)
@pytest.mark.parametrize(
    "content, values, prefix, expected_result",
    [
        ("", {}, None, True),
        ("", {}, "GDS", True),
        ("((placeholder))", {"placeholder": ""}, "GDS", True),
        ("((placeholder))", {"placeholder": "Some content"}, None, False),
        ("Some content", {}, "GDS", False),
    ],
)
def test_is_message_empty_sms_templates(content, values, prefix, expected_result, template_class):
    template = template_class(
        {"content": content, "template_type": "sms"},
        prefix=prefix,
    )
    template.sender = None
    template.values = values
    assert template.is_message_empty() == expected_result


@pytest.mark.parametrize(
    "template_class, template_type",
    (
        (HTMLEmailTemplate, "email"),
        (LetterPrintTemplate, "letter"),
    ),
)
@pytest.mark.parametrize(
    "content, values, expected_result",
    [
        ("", {}, True),
        ("((placeholder))", {"placeholder": ""}, True),
        ("((placeholder))", {"placeholder": "   \t   \r\n"}, True),
        ("((placeholder))", {"placeholder": "Some content"}, False),
        ("((placeholder??show_or_hide))", {"placeholder": False}, True),
        ("Some content", {}, False),
        ("((placeholder)) some content", {"placeholder": ""}, False),
        ("Some content ((placeholder))", {"placeholder": ""}, False),
    ],
)
def test_is_message_empty_email_and_letter_templates(
    template_class,
    template_type,
    content,
    values,
    expected_result,
):
    template = template_class(
        {
            "content": content,
            "subject": "Hi",
            "template_type": template_class.template_type,
        }
    )
    template.sender = None
    template.values = values
    assert template.is_message_empty() == expected_result


@pytest.mark.parametrize(
    "template_class, template_type",
    (
        (HTMLEmailTemplate, "email"),
        (LetterPrintTemplate, "letter"),
    ),
)
@pytest.mark.parametrize(
    "content, values",
    [
        ("Some content", {}),
        ("((placeholder)) some content", {"placeholder": ""}),
        ("Some content ((placeholder))", {"placeholder": ""}),
        pytest.param(
            "((placeholder))",
            {"placeholder": "Some content"},
            marks=pytest.mark.xfail(raises=AssertionError),
        ),
    ],
)
def test_is_message_empty_email_and_letter_templates_tries_not_to_count_chars(
    mocker,
    template_class,
    template_type,
    content,
    values,
):
    template = template_class(
        {
            "content": content,
            "subject": "Hi",
            "template_type": template_type,
        }
    )
    mock_content = mocker.patch.object(
        template_class,
        "content_count",
        create=True,
        new_callable=mock.PropertyMock,
        return_value=None,
    )
    template.values = values
    template.is_message_empty()
    assert mock_content.called is False


@pytest.mark.parametrize(
    "template_class, template_type, extra_args, expected_field_calls",
    [
        (PlainTextEmailTemplate, "email", {}, [mock.call("content", {}, html="passthrough", markdown_lists=True)]),
        (
            HTMLEmailTemplate,
            "email",
            {},
            [
                mock.call("subject", {}, html="escape", redact_missing_personalisation=False),
                mock.call("content", {}, html="escape", markdown_lists=True, redact_missing_personalisation=False),
                mock.call("content", {}, html="escape", markdown_lists=True),
            ],
        ),
        (
            SMSMessageTemplate,
            "sms",
            {},
            [
                mock.call("content"),  # This is to get the placeholders
                mock.call("content", {}, html="passthrough"),
            ],
        ),
        (
            SMSPreviewTemplate,
            "sms",
            {},
            [
                mock.call("((phone number))", {}, with_brackets=False, html="escape"),
                mock.call("content", {}, html="escape", redact_missing_personalisation=False),
            ],
        ),
        (
            LetterPreviewTemplate,
            "letter",
            {"contact_block": "www.gov.uk"},
            [
                mock.call("subject", {}, html="escape", redact_missing_personalisation=False),
                mock.call("content", {}, html="escape", markdown_lists=True, redact_missing_personalisation=False),
                mock.call(
                    (
                        "((address line 1))\n"
                        "((address line 2))\n"
                        "((address line 3))\n"
                        "((address line 4))\n"
                        "((address line 5))\n"
                        "((address line 6))\n"
                        "((address line 7))"
                    ),
                    {},
                    with_brackets=False,
                    html="escape",
                ),
                mock.call("www.gov.uk", {}, html="escape", redact_missing_personalisation=False),
            ],
        ),
        (
            SMSPreviewTemplate,
            "sms",
            {"redact_missing_personalisation": True},
            [
                mock.call("((phone number))", {}, with_brackets=False, html="escape"),
                mock.call("content", {}, html="escape", redact_missing_personalisation=True),
            ],
        ),
        (
            SMSBodyPreviewTemplate,
            "sms",
            {},
            [
                mock.call("content", {}, html="escape", redact_missing_personalisation=True),
            ],
        ),
        (
            LetterPreviewTemplate,
            "letter",
            {"contact_block": "www.gov.uk", "redact_missing_personalisation": True},
            [
                mock.call("subject", {}, html="escape", redact_missing_personalisation=True),
                mock.call("content", {}, html="escape", markdown_lists=True, redact_missing_personalisation=True),
                mock.call(
                    (
                        "((address line 1))\n"
                        "((address line 2))\n"
                        "((address line 3))\n"
                        "((address line 4))\n"
                        "((address line 5))\n"
                        "((address line 6))\n"
                        "((address line 7))"
                    ),
                    {},
                    with_brackets=False,
                    html="escape",
                ),
                mock.call("www.gov.uk", {}, html="escape", redact_missing_personalisation=True),
            ],
        ),
    ],
)
@mock.patch("notifications_utils.template.Field.__init__", return_value=None)
@mock.patch("notifications_utils.template.Field.__str__", return_value="1\n2\n3\n4\n5\n6\n7\n8")
def test_templates_handle_html_and_redacting(
    mock_field_str,
    mock_field_init,
    template_class,
    template_type,
    extra_args,
    expected_field_calls,
):
    assert str(
        template_class({"content": "content", "subject": "subject", "template_type": template_type}, **extra_args)
    )
    assert mock_field_init.call_args_list == expected_field_calls


@pytest.mark.parametrize(
    "template_class, template_type, extra_args, expected_remove_whitespace_calls",
    [
        (
            PlainTextEmailTemplate,
            "email",
            {},
            [
                mock.call("\n\ncontent"),
                mock.call(Markup("subject")),
                mock.call(Markup("subject")),
            ],
        ),
        (
            HTMLEmailTemplate,
            "email",
            {},
            [
                mock.call(Markup("subject")),
                mock.call(
                    '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">content</p>'
                ),
                mock.call("\n\ncontent"),
                mock.call(Markup("subject")),
                mock.call(Markup("subject")),
            ],
        ),
        (
            SMSMessageTemplate,
            "sms",
            {},
            [
                mock.call("content"),
            ],
        ),
        (
            SMSPreviewTemplate,
            "sms",
            {},
            [
                mock.call("content"),
            ],
        ),
        (
            SMSBodyPreviewTemplate,
            "sms",
            {},
            [
                mock.call("content"),
            ],
        ),
        (
            LetterPreviewTemplate,
            "letter",
            {"contact_block": "www.gov.uk"},
            [
                mock.call(Markup("subject")),
                mock.call(Markup("<p>content</p>")),
                mock.call(Markup("www.gov.uk")),
                mock.call(Markup("subject")),
                mock.call(Markup("subject")),
            ],
        ),
    ],
)
@mock.patch("notifications_utils.template.remove_whitespace_before_punctuation", side_effect=lambda x: x)
def test_templates_remove_whitespace_before_punctuation(
    mock_remove_whitespace,
    template_class,
    template_type,
    extra_args,
    expected_remove_whitespace_calls,
):
    template = template_class(
        {"content": "content", "subject": "subject", "template_type": template_type}, **extra_args
    )

    assert str(template)

    if hasattr(template, "subject"):
        assert template.subject

    assert mock_remove_whitespace.call_args_list == expected_remove_whitespace_calls


@pytest.mark.parametrize(
    "template_class, template_type, extra_args, expected_calls",
    [
        (
            PlainTextEmailTemplate,
            "email",
            {},
            [
                mock.call("\n\ncontent"),
                mock.call(Markup("subject")),
            ],
        ),
        (
            HTMLEmailTemplate,
            "email",
            {},
            [
                mock.call(
                    '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">content</p>'
                ),
                mock.call("\n\ncontent"),
                mock.call(Markup("subject")),
            ],
        ),
        (SMSMessageTemplate, "sms", {}, []),
        (SMSPreviewTemplate, "sms", {}, []),
        (SMSBodyPreviewTemplate, "sms", {}, []),
        (
            LetterPreviewTemplate,
            "letter",
            {"contact_block": "www.gov.uk"},
            [
                mock.call(Markup("subject")),
                mock.call(Markup("<p>content</p>")),
            ],
        ),
    ],
)
@mock.patch("notifications_utils.template.make_quotes_smart", side_effect=lambda x: x)
@mock.patch("notifications_utils.template.replace_hyphens_with_en_dashes", side_effect=lambda x: x)
def test_templates_make_quotes_smart_and_dashes_en(
    mock_en_dash_replacement,
    mock_smart_quotes,
    template_class,
    template_type,
    extra_args,
    expected_calls,
):
    template = template_class(
        {"content": "content", "subject": "subject", "template_type": template_type}, **extra_args
    )

    assert str(template)

    if hasattr(template, "subject"):
        assert template.subject

    mock_smart_quotes.assert_has_calls(expected_calls)
    mock_en_dash_replacement.assert_has_calls(expected_calls)


@pytest.mark.parametrize(
    "content",
    (
        "first.o'last@example.com",
        "first.o’last@example.com",
    ),
)
@pytest.mark.parametrize(
    "template_class",
    (
        HTMLEmailTemplate,
        PlainTextEmailTemplate,
    ),
)
def test_no_smart_quotes_in_email_addresses(template_class, content):
    template = template_class(
        {
            "content": content,
            "subject": content,
            "template_type": "email",
        }
    )
    assert "first.o'last@example.com" in str(template)
    assert template.subject == "first.o'last@example.com"


def test_smart_quotes_removed_from_long_template_in_under_a_second():
    long_string = "a" * 100000
    template = PlainTextEmailTemplate(
        {
            "content": long_string,
            "subject": "",
            "template_type": "email",
        }
    )

    start_time = process_time()

    str(template)

    assert process_time() - start_time < 1


@pytest.mark.parametrize(
    "template_instance, expected_placeholders",
    [
        (
            SMSMessageTemplate(
                {"content": "((content))", "subject": "((subject))", "template_type": "sms"},
            ),
            ["content"],
        ),
        (
            SMSPreviewTemplate(
                {"content": "((content))", "subject": "((subject))", "template_type": "sms"},
            ),
            ["content"],
        ),
        (
            SMSBodyPreviewTemplate(
                {"content": "((content))", "subject": "((subject))", "template_type": "sms"},
            ),
            ["content"],
        ),
        (
            PlainTextEmailTemplate(
                {"content": "((content))", "subject": "((subject))", "template_type": "email"},
            ),
            ["subject", "content"],
        ),
        (
            HTMLEmailTemplate(
                {"content": "((content))", "subject": "((subject))", "template_type": "email"},
            ),
            ["subject", "content"],
        ),
        (
            LetterPreviewTemplate(
                {"content": "((content))", "subject": "((subject))", "template_type": "letter"},
                contact_block="((contact_block))",
            ),
            ["contact_block", "subject", "content"],
        ),
    ],
)
def test_templates_extract_placeholders(
    template_instance,
    expected_placeholders,
):
    assert template_instance.placeholders == OrderedSet(expected_placeholders)


def test_html_template_can_inject_personalisation_with_special_characters():
    template_content = "This is something text with (( this&that )) HTML special character personalisation <>."
    personalisation = {"this&that": "some very lovely &"}

    result = str(
        HTMLEmailTemplate({"content": template_content, "subject": "", "template_type": "email"}, personalisation)
    )
    assert (
        "This is something text with some very lovely &amp; HTML special character personalisation &lt;&gt;." in result
    )


@pytest.mark.parametrize(
    "address, expected",
    [
        (
            {
                "address line 1": "line 1",
                "address line 2": "line 2",
                "address line 3": "line 3",
                "address line 4": "line 4",
                "address line 5": "line 5",
                "address line 6": "line 6",
                "postcode": "n14w q",
            },
            (
                "<ul>"
                "<li>line 1</li>"
                "<li>line 2</li>"
                "<li>line 3</li>"
                "<li>line 4</li>"
                "<li>line 5</li>"
                "<li>line 6</li>"
                "<li>N1 4WQ</li>"
                "</ul>"
            ),
        ),
        (
            {
                "addressline1": "line 1",
                "addressline2": "line 2",
                "addressline3": "line 3",
                "addressline4": "line 4",
                "addressline5": "line 5",
                "addressLine6": "line 6",
                "postcode": "not a postcode",
            },
            (
                "<ul>"
                "<li>line 1</li>"
                "<li>line 2</li>"
                "<li>line 3</li>"
                "<li>line 4</li>"
                "<li>line 5</li>"
                "<li>line 6</li>"
                "<li>not a postcode</li>"
                "</ul>"
            ),
        ),
        (
            {
                "address line 1": "line 1",
                "postcode": "n1 4wq",
            },
            (
                "<ul>"
                "<li>line 1</li>"
                '<li><span class="placeholder-no-brackets">address line 2</span></li>'
                '<li><span class="placeholder-no-brackets">address line 3</span></li>'
                '<li><span class="placeholder-no-brackets">address line 4</span></li>'
                '<li><span class="placeholder-no-brackets">address line 5</span></li>'
                '<li><span class="placeholder-no-brackets">address line 6</span></li>'
                # Postcode is not normalised until the address is complete
                "<li>n1 4wq</li>"
                "</ul>"
            ),
        ),
        (
            {
                "addressline1": "line 1",
                "addressline2": "line 2",
                "addressline3": None,
                "addressline6": None,
                "postcode": "N1 4Wq",
            },
            ("<ul><li>line 1</li><li>line 2</li><li>N1 4WQ</li></ul>"),
        ),
        (
            {
                "addressline1": "line 1",
                "addressline2": "line 2     ,   ",
                "addressline3": "\t     ,",
                "postcode": "N1 4WQ",
            },
            ("<ul><li>line 1</li><li>line 2</li><li>N1 4WQ</li></ul>"),
        ),
        (
            {
                "addressline1": "line 1",
                "addressline2": "line 2",
                "postcode": "SW1A 1AA",  # ignored in favour of line 7
                "addressline7": "N1 4WQ",
            },
            ("<ul><li>line 1</li><li>line 2</li><li>N1 4WQ</li></ul>"),
        ),
        (
            {
                "addressline1": "line 1",
                "addressline2": "line 2",
                "addressline7": "N1 4WQ",  # means postcode isn’t needed
            },
            ("<ul><li>line 1</li><li>line 2</li><li>N1 4WQ</li></ul>"),
        ),
    ],
)
@pytest.mark.parametrize("template_class", (LetterPreviewTemplate, LetterPrintTemplate))
def test_letter_address_format(template_class, address, expected):
    template = BeautifulSoup(
        str(
            template_class(
                {"content": "", "subject": "", "template_type": "letter"},
                address,
            )
        ),
        features="html.parser",
    )
    assert str(template.select_one("#to ul")) == expected


@freeze_time("2001-01-01 12:00:00.000000")
@pytest.mark.parametrize(
    "markdown, expected",
    [
        (
            ("Here is a list of bullets:\n\n* one\n* two\n* three\n\nNew paragraph"),
            ("<ul>\n<li>one</li>\n<li>two</li>\n<li>three</li>\n</ul>\n<p>New paragraph</p>\n"),
        ),
        (
            ("# List title:\n\n* one\n* two\n* three\n"),
            ("<h2>List title:</h2>\n<ul>\n<li>one</li>\n<li>two</li>\n<li>three</li>\n</ul>\n"),
        ),
        (
            ("Here’s an ordered list:\n\n1. one\n2. two\n3. three\n"),
            ("<p>Here’s an ordered list:</p><ol>\n<li>one</li>\n<li>two</li>\n<li>three</li>\n</ol>"),
        ),
    ],
)
def test_lists_in_combination_with_other_elements_in_letters(markdown, expected):
    assert expected in str(
        LetterPreviewTemplate(
            {"content": markdown, "subject": "Hello", "template_type": "letter"},
            {},
        )
    )


@pytest.mark.parametrize(
    "template_class",
    [
        SMSMessageTemplate,
        SMSPreviewTemplate,
    ],
)
def test_message_too_long_ignoring_prefix(template_class):
    body = ("b" * 917) + "((foo))"
    template = template_class(
        {"content": body, "template_type": template_class.template_type}, prefix="a" * 100, values={"foo": "cc"}
    )
    # content length is prefix + 919 characters (more than limit of 918)
    assert template.is_message_too_long() is True


@pytest.mark.parametrize(
    "template_class",
    [
        SMSMessageTemplate,
        SMSPreviewTemplate,
    ],
)
def test_message_is_not_too_long_ignoring_prefix(template_class):
    body = ("b" * 917) + "((foo))"
    template = template_class(
        {"content": body, "template_type": template_class.template_type},
        prefix="a" * 100,
        values={"foo": "c"},
    )
    # content length is prefix + 918 characters (not more than limit of 918)
    assert template.is_message_too_long() is False


@pytest.mark.parametrize(
    "template_class, template_type, kwargs",
    [
        (HTMLEmailTemplate, "email", {}),
        (PlainTextEmailTemplate, "email", {}),
        (LetterPreviewTemplate, "letter", {}),
    ],
)
def test_message_too_long_limit_bigger_or_nonexistent_for_non_sms_templates(template_class, template_type, kwargs):
    body = "a" * 1000
    template = template_class({"content": body, "subject": "foo", "template_type": template_type}, **kwargs)
    assert template.is_message_too_long() is False


@pytest.mark.parametrize(
    "template_class, template_type, kwargs",
    [
        (HTMLEmailTemplate, "email", {}),
        (PlainTextEmailTemplate, "email", {}),
    ],
)
def test_content_size_in_bytes_for_email_messages(template_class, template_type, kwargs):
    # Message being a Markup objects adds 81 bytes overhead, so it's 100 bytes for 100 x 'b' and 81 bytes overhead
    body = "b" * 100
    template = template_class({"content": body, "subject": "foo", "template_type": template_type}, **kwargs)
    assert template.content_size_in_bytes == 100


@pytest.mark.parametrize(
    "template_class, template_type, kwargs",
    [
        (HTMLEmailTemplate, "email", {}),
        (PlainTextEmailTemplate, "email", {}),
    ],
)
def test_message_too_long_for_a_too_big_email_message(template_class, template_type, kwargs):
    # Message being a Markup objects adds 81 bytes overhead, taking our message over the limit
    body = "b" * 2000001
    template = template_class({"content": body, "subject": "foo", "template_type": template_type}, **kwargs)
    assert template.is_message_too_long() is True


@pytest.mark.parametrize(
    "template_class, template_type, kwargs",
    [
        (HTMLEmailTemplate, "email", {}),
        (PlainTextEmailTemplate, "email", {}),
    ],
)
def test_message_too_long_for_an_email_message_within_limits(template_class, template_type, kwargs):
    body = "b" * 1999999
    template = template_class({"content": body, "subject": "foo", "template_type": template_type}, **kwargs)
    assert template.is_message_too_long() is False


@pytest.mark.parametrize(
    ("content,expected_preview_markup,"),
    [
        (
            "a\n\n\nb",
            "<p>a</p><p>b</p>",
        ),
        (
            "a\n\n* one\n* two\n* three\nand a half\n\n\n\n\nfoo",
            "<p>a</p><ul>\n<li>one</li>\n<li>two</li>\n<li>three<br>and a half</li>\n</ul>\n<p>foo</p>",
        ),
    ],
)
def test_multiple_newlines_in_letters(
    content,
    expected_preview_markup,
):
    assert expected_preview_markup in str(
        LetterPreviewTemplate({"content": content, "subject": "foo", "template_type": "letter"})
    )


@pytest.mark.parametrize(
    "subject",
    [
        " no break ",
        " no\tbreak ",
        "\tno break\t",
        "no \r\nbreak",
        "no \nbreak",
        "no \rbreak",
        "\rno break\n",
    ],
)
@pytest.mark.parametrize(
    "template_class, template_type, extra_args",
    [
        (PlainTextEmailTemplate, "email", {}),
        (HTMLEmailTemplate, "email", {}),
        (LetterPreviewTemplate, "letter", {}),
    ],
)
def test_whitespace_in_subjects(template_class, template_type, subject, extra_args):
    template_instance = template_class(
        {"content": "foo", "subject": subject, "template_type": template_type}, **extra_args
    )
    assert template_instance.subject == "no break"


@pytest.mark.parametrize(
    "template_class",
    [
        HTMLEmailTemplate,
        PlainTextEmailTemplate,
    ],
)
def test_whitespace_in_subject_placeholders(template_class):
    assert (
        template_class(
            {"content": "", "subject": "\u200c Your tax   ((status))", "template_type": "email"},
            values={"status": " is\ndue "},
        ).subject
        == "Your tax is due"
    )


@pytest.mark.parametrize(
    "template_class, expected_output",
    [
        (
            PlainTextEmailTemplate,
            "paragraph one\n\n\xa0\n\nparagraph two",
        ),
        (
            HTMLEmailTemplate,
            (
                '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">paragraph one</p>'
                '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">&nbsp;</p>'
                '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">paragraph two</p>'
            ),
        ),
    ],
)
def test_govuk_email_whitespace_hack(template_class, expected_output):
    template_instance = template_class(
        {
            "content": "paragraph one\n\n&nbsp;\n\nparagraph two",
            "subject": "foo",
            "template_type": "email",
        }
    )
    assert expected_output in str(template_instance)


def test_letter_preview_uses_non_breaking_hyphens():
    assert "non\u2011breaking" in str(
        LetterPreviewTemplate(
            {
                "content": "non-breaking",
                "subject": "foo",
                "template_type": "letter",
            }
        )
    )
    assert "–" in str(
        LetterPreviewTemplate(
            {
                "content": "en dash - not hyphen - when set with spaces",
                "subject": "foo",
                "template_type": "letter",
            }
        )
    )


@freeze_time("2001-01-01 12:00:00.000000")
def test_nested_lists_in_lettr_markup():
    template_content = str(
        LetterPreviewTemplate(
            {
                "content": (
                    "nested list:\n\n1. one\n2. two\n3. three\n  - three one\n  - three two\n  - three three\n"
                ),
                "subject": "foo",
                "template_type": "letter",
            }
        )
    )

    assert (
        "      <p>\n"
        "        1 January 2001\n"
        "      </p>\n"
        # Note that the H1 tag has no trailing whitespace
        "      <h1>foo</h1>\n"
        "      <p>nested list:</p><ol>\n"
        "<li>one</li>\n"
        "<li>two</li>\n"
        "<li>three<ul>\n"
        "<li>three one</li>\n"
        "<li>three two</li>\n"
        "<li>three three</li>\n"
        "</ul></li>\n"
        "</ol>\n"
        "\n"
        "    </div>\n"
        "  </body>\n"
        "</html>"
    ) in template_content


def test_that_print_template_is_the_same_as_preview():
    assert dir(LetterPreviewTemplate) == dir(LetterPrintTemplate)
    assert os.path.basename(LetterPreviewTemplate.jinja_template.filename) == "preview.jinja2"
    assert os.path.basename(LetterPrintTemplate.jinja_template.filename) == "print.jinja2"


def test_plain_text_email_whitespace():
    email = PlainTextEmailTemplate(
        {
            "template_type": "email",
            "subject": "foo",
            "content": (
                "# Heading\n"
                "\n"
                "1. one\n"
                "2. two\n"
                "3. three\n"
                "\n"
                "***\n"
                "\n"
                "# Heading\n"
                "\n"
                "Paragraph\n"
                "\n"
                "Paragraph\n"
                "\n"
                "^ callout\n"
                "\n"
                "1. one not four\n"
                "1. two not five"
            ),
        }
    )
    assert str(email) == (
        "Heading\n"
        "=================================================================\n"
        "\n"
        "1. one\n"
        "2. two\n"
        "3. three\n"
        "\n"
        "=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=\n"
        "\n"
        "\n"
        "Heading\n"
        "=================================================================\n"
        "\n"
        "Paragraph\n"
        "\n"
        "Paragraph\n"
        "\n"
        "callout\n"
        "\n"
        "1. one not four\n"
        "2. two not five\n"
    )


@pytest.mark.parametrize(
    "renderer, template_type, expected_content",
    (
        (
            PlainTextEmailTemplate,
            "email",
            "Heading link: https://example.com\n=================================================================\n",
        ),
        (
            HTMLEmailTemplate,
            "email",
            (
                '<h2 style="Margin: 0 0 15px 0; padding: 10px 0 0 0; font-size: 27px; '
                'line-height: 35px; font-weight: bold; color: #0B0C0C;">'
                'Heading <a style="word-wrap: break-word; color: #1D70B8;" href="https://example.com">link</a>'
                "</h2>"
            ),
        ),
        (
            LetterPreviewTemplate,
            "letter",
            ("<h2>Heading [link](https://example.com)</h2>"),
        ),
        (
            LetterPrintTemplate,
            "letter",
            ("<h2>Heading [link](https://example.com)</h2>"),
        ),
    ),
)
def test_heading_only_template_renders(renderer, template_type, expected_content):
    assert expected_content in str(
        renderer(
            {
                "subject": "foo",
                "content": ("# Heading [link](https://example.com)"),
                "template_type": template_type,
            }
        )
    )


@pytest.mark.parametrize(
    "template_class",
    [
        LetterPreviewTemplate,
        LetterPrintTemplate,
    ],
)
@pytest.mark.parametrize(
    "filename, expected_html_class",
    [
        ("example.png", 'class="png"'),
        ("example.svg", 'class="svg"'),
    ],
)
def test_image_class_applied_to_logo(template_class, filename, expected_html_class):
    assert expected_html_class in str(
        template_class(
            {"content": "Foo", "subject": "Subject", "template_type": "letter"},
            logo_file_name=filename,
        )
    )


@pytest.mark.parametrize(
    "template_class",
    [
        LetterPreviewTemplate,
        LetterPrintTemplate,
    ],
)
def test_image_not_present_if_no_logo(template_class):
    # can't test that the html doesn't move in utils - tested in template preview instead
    assert "<img" not in str(
        template_class(
            {"content": "Foo", "subject": "Subject", "template_type": "letter"},
            logo_file_name=None,
        )
    )


@pytest.mark.parametrize(
    "content",
    (
        "The     quick brown fox.\n\n\n\n\nJumps over the lazy dog.   \nSingle linebreak above.",
        "\n   \nThe quick brown fox.  \n\n          Jumps over the lazy dog   .  \nSingle linebreak above. \n  \n \n",
    ),
)
@pytest.mark.parametrize(
    "template_class, expected",
    (
        (
            SMSBodyPreviewTemplate,
            "The quick brown fox.\n\nJumps over the lazy dog.\nSingle linebreak above.",
        ),
        (
            SMSMessageTemplate,
            "The quick brown fox.\n\nJumps over the lazy dog.\nSingle linebreak above.",
        ),
        (
            SMSPreviewTemplate,
            (
                "\n\n"
                '<div class="sms-message-wrapper">\n'
                "  The quick brown fox.<br><br>Jumps over the lazy dog.<br>Single linebreak above.\n"
                "</div>"
            ),
        ),
    ),
)
def test_text_messages_collapse_consecutive_whitespace(
    template_class,
    content,
    expected,
):
    template = template_class({"content": content, "template_type": "sms"})
    assert str(template) == expected
    assert (
        template.content_count == 70 == len("The quick brown fox.\n\nJumps over the lazy dog.\nSingle linebreak above.")
    )


@pytest.mark.parametrize(
    "template_class, template_data, expect_content",
    (
        (
            LetterPreviewTemplate,
            {"template_type": "letter", "subject": "foo", "content": "[Example](((var)))"},
            "<p>[Example](<span class='placeholder'>&#40;&#40;var&#41;&#41;</span>)</p>",
        ),
        (
            LetterPreviewTemplate,
            {"template_type": "letter", "subject": "foo", "content": "[Example](https://blah.blah/?query=((var)))"},
            "<p>[Example](https://blah.blah/?query=<span class='placeholder'>&#40;&#40;var&#41;&#41;</span>)</p>",
        ),
        (
            LetterPreviewTemplate,
            {"template_type": "letter", "subject": "foo", "content": "[Example](pre((var))post)"},
            "<p>[Example](pre<span class='placeholder'>&#40;&#40;var&#41;&#41;</span>post)</p>",
        ),
        (
            LetterPreviewTemplate,
            {"template_type": "letter", "subject": "foo", "content": "QR: ((var))"},
            (
                "<p>\n"
                "<div class='qrcode-placeholder'>\n"
                "    <div class='qrcode-placeholder-border'></div>\n"
                "    <div class='qrcode-placeholder-content'>\n"
                "        <span class='qrcode-placeholder-content-background'><span class='placeholder'>&#40;&#40;var&#41;&#41;</span></span>\n"  # noqa
                "    </div>\n"
                "</div>\n"
                "</p>"
            ),
        ),
        (
            LetterPreviewTemplate,
            {"template_type": "letter", "subject": "foo", "content": "QR:https://blah.blah/?query=((var))"},
            (
                "<p>\n"
                "<div class='qrcode-placeholder'>\n"
                "    <div class='qrcode-placeholder-border'></div>\n"
                "    <div class='qrcode-placeholder-content'>\n"
                "        <span class='qrcode-placeholder-content-background'>https://blah.blah/?query=<span class='placeholder'>&#40;&#40;var&#41;&#41;</span></span>\n"  # noqa
                "    </div>\n"
                "</div>\n"
                "</p>"
            ),
        ),
        (
            LetterPreviewTemplate,
            {"template_type": "letter", "subject": "foo", "content": "qr:pre((var))post"},
            (
                "<p>\n<div class='qrcode-placeholder'>\n"
                "    <div class='qrcode-placeholder-border'></div>\n"
                "    <div class='qrcode-placeholder-content'>\n"
                "        <span class='qrcode-placeholder-content-background'>pre<span class='placeholder'>&#40;&#40;var&#41;&#41;</span>post</span>\n"  # noqa
                "    </div>\n"
                "</div>\n"
                "</p>"
            ),
        ),
    ),
)
def test_links_with_personalisation(template_class, template_data, expect_content):
    assert expect_content in str(template_class(template_data))


@pytest.mark.parametrize(
    "content, values, should_error",
    (
        ("i am some clean content", {}, False),
        ("i am some short ((content))", {"content": "content"}, False),
        ("i am some long ((content))", {"content": "content" * 100}, False),
        ("i am a long qr code\n\nqr: ((content))", {"content": "content" * 100}, True),
    ),
)
def test_letter_qr_codes_with_too_much_data(content, values, should_error):
    template = LetterPreviewTemplate({"template_type": "letter", "subject": "foo", "content": content}, values)

    error = template.has_qr_code_with_too_much_data()

    if should_error:
        assert error.data == "content" * 100
        assert error.max_bytes == 504
        assert error.num_bytes == 700
    else:
        assert error is None


@pytest.mark.parametrize(
    "extra_template_kwargs, should_have_notify_tag",
    (
        ({}, True),
        ({"includes_first_page": True}, True),
        ({"includes_first_page": False}, False),
    ),
)
def test_rendered_letter_template_for_print_can_toggle_notify_tag_and_always_hides_barcodes(
    extra_template_kwargs, should_have_notify_tag
):
    template = LetterPrintTemplate(
        {"template_type": "letter", "subject": "subject", "content": "content"}, {}, **extra_template_kwargs
    )
    assert ("content: 'NOTIFY';" in str(template)) == should_have_notify_tag
    assert "#mdi,\n  #barcode,\n  #qrcode {\n    display: none;\n  }" in str(template).strip()


@pytest.mark.parametrize("includes_first_page", [True, False])
def test_rendered_letter_template_for_preview_displays_barcodes_only_if_file_includes_first_page(includes_first_page):
    template = LetterPreviewTemplate(
        template={"template_type": "letter", "subject": "subject", "content": "content"},
        includes_first_page=includes_first_page,
    )
    assert (
        "#mdi,\n  #barcode,\n  #qrcode {\n    display: none;\n  }" in str(template).strip()
    ) is not includes_first_page


@pytest.mark.parametrize(
    "template_class, expected_content",
    (
        (
            HTMLEmailTemplate,
            (
                '<hr style="border: 0; height: 1px; background: #B1B4B6; Margin: 30px 0 30px 0;">'
                '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">'
                '<a style="word-wrap: break-word; color: #1D70B8;" href="https://www.example.com">'
                "Unsubscribe from these emails"
                "</a>"
                "</p>\n"
            ),
        ),
        (
            PlainTextEmailTemplate,
            (
                "=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=\n"
                "\n"
                "Unsubscribe from these emails: https://www.example.com\n"
            ),
        ),
    ),
)
def test_unsubscribe_link_is_rendered(
    template_class,
    expected_content,
):
    assert expected_content in (
        str(
            template_class(
                {"content": "Hello world", "subject": "subject", "template_type": "email"},
                {},
                unsubscribe_link="https://www.example.com",
            )
        )
    )
    assert expected_content not in (
        str(
            template_class(
                {"content": "Hello world", "subject": "subject", "template_type": "email"},
                {},
            )
        )
    )


def test_html_entities_in_html_email():
    assert "[ ] ( ) * / # &amp; &nbsp; ^" in str(
        HTMLEmailTemplate(
            {
                "content": "&lsqb; &rsqb; &lpar; &rpar; &ast; &sol; &num; &amp; &nbsp; &Hat;",
                "subject": "subject",
                "template_type": "email",
            },
        )
    )


def test_html_entities_in_plain_text_email():
    assert "[ ] ( ) * / # & \xa0 ^\n" == str(
        PlainTextEmailTemplate(
            {
                "content": "&lsqb; &rsqb; &lpar; &rpar; &ast; &sol; &num; &amp; &nbsp; &Hat;",
                "subject": "subject",
                "template_type": "email",
            }
        )
    )
