import pytest
from bs4 import BeautifulSoup

from notifications_utils.field import Field
from notifications_utils.markdown import (
    notify_email_markdown,
    notify_letter_preview_markdown,
    notify_letter_qrcode_validator,
    notify_plain_text_email_markdown,
)
from notifications_utils.take import Take
from notifications_utils.template import HTMLEmailTemplate


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com",
        "http://www.gov.uk/",
        "https://www.gov.uk/",
        "http://service.gov.uk",
        "http://service.gov.uk/blah.ext?q=a%20b%20c&order=desc#fragment",
        pytest.param("http://service.gov.uk/blah.ext?q=one two three", marks=pytest.mark.xfail),
    ],
)
def test_makes_links_out_of_URLs(url):
    link = f'<a style="word-wrap: break-word; color: #1D70B8;" href="{url}">{url}</a>'
    assert notify_email_markdown(url) == (
        f'<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">{link}</p>'
    )


@pytest.mark.parametrize(
    "input, output",
    [
        (
            ("this is some text with a link http://example.com in the middle"),
            (
                "this is some text with a link "
                '<a style="word-wrap: break-word; color: #1D70B8;" href="http://example.com">http://example.com</a>'
                " in the middle"
            ),
        ),
        (
            ("this link is in brackets (http://example.com)"),
            (
                "this link is in brackets "
                '(<a style="word-wrap: break-word; color: #1D70B8;" href="http://example.com">http://example.com</a>)'
            ),
        ),
    ],
)
def test_makes_links_out_of_URLs_in_context(input, output):
    assert notify_email_markdown(input) == (
        f'<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">{output}</p>'
    )


@pytest.mark.parametrize(
    "url",
    [
        "example.com",
        "www.example.com",
        "ftp://example.com",
        "test@example.com",
        "mailto:test@example.com",
        '<a href="https://example.com">Example</a>',
    ],
)
def test_doesnt_make_links_out_of_invalid_urls(url):
    assert notify_email_markdown(url) == (
        f'<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">{url}</p>'
    )


def test_handles_placeholders_in_urls():
    assert notify_email_markdown("http://example.com/?token=<span class='placeholder'>((token))</span>&key=1") == (
        '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">'
        '<a style="word-wrap: break-word; color: #1D70B8;" href="http://example.com/?token=">'
        "http://example.com/?token="
        "</a>"
        "<span class='placeholder'>((token))</span>&amp;key=1"
        "</p>"
    )


@pytest.mark.parametrize(
    "url, expected_html, expected_html_in_template",
    [
        (
            """https://example.com"onclick="alert('hi')""",
            """<a style="word-wrap: break-word; color: #1D70B8;" href="https://example.com%22onclick=%22alert%28%27hi">https://example.com"onclick="alert('hi</a>')""",
            """<a style="word-wrap: break-word; color: #1D70B8;" href="https://example.com%22onclick=%22alert%28%27hi">https://example.com"onclick="alert('hi</a>‘)""",
        ),
        (
            """https://example.com/login?redirect=%2Fhomepage%3Fsuccess=true%26page=blue""",
            """<a style="word-wrap: break-word; color: #1D70B8;" href="https://example.com/login?redirect=%2Fhomepage%3Fsuccess=true%26page=blue">https://example.com/login?redirect=%2Fhomepage%3Fsuccess=true%26page=blue</a>""",
            """<a style="word-wrap: break-word; color: #1D70B8;" href="https://example.com/login?redirect=%2Fhomepage%3Fsuccess=true%26page=blue">https://example.com/login?redirect=%2Fhomepage%3Fsuccess=true%26page=blue</a>""",
        ),
        (
            """https://example.com"style='text-decoration:blink'""",
            """<a style="word-wrap: break-word; color: #1D70B8;" href="https://example.com%22style=%27text-decoration:blink">https://example.com"style='text-decoration:blink</a>'""",
            """<a style="word-wrap: break-word; color: #1D70B8;" href="https://example.com%22style=%27text-decoration:blink">https://example.com"style='text-decoration:blink</a>’""",
        ),
    ],
)
def test_URLs_get_escaped(url, expected_html, expected_html_in_template):
    assert notify_email_markdown(url) == (
        f'<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">{expected_html}</p>'
    )
    assert expected_html_in_template in str(
        HTMLEmailTemplate(
            {
                "content": url,
                "subject": "",
                "template_type": "email",
            }
        )
    )


@pytest.mark.parametrize(
    "markdown_function, expected_output",
    [
        (
            notify_email_markdown,
            (
                '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">'
                '<a style="word-wrap: break-word; color: #1D70B8;" href="https://example.com">'
                "https://example.com"
                "</a>"
                "</p>"
                '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">'
                "Next paragraph"
                "</p>"
            ),
        ),
        (
            notify_plain_text_email_markdown,
            ("\n\nhttps://example.com\n\nNext paragraph"),
        ),
    ],
)
def test_preserves_whitespace_when_making_links(markdown_function, expected_output):
    assert markdown_function("https://example.com\n\nNext paragraph") == expected_output


@pytest.mark.parametrize(
    "markdown_function, expected",
    (
        [notify_letter_preview_markdown, 'print("hello")'],
        [notify_email_markdown, 'print("hello")'],
        [notify_plain_text_email_markdown, 'print("hello")'],
    ),
)
def test_block_code(markdown_function, expected):
    assert markdown_function('```\nprint("hello")\n```') == expected


@pytest.mark.parametrize(
    "markdown_function, expected",
    (
        [notify_letter_preview_markdown, ("<p>inset text</p>")],
        [
            notify_email_markdown,
            (
                '<div style="Margin: 0 0 20px 0;">'
                "<blockquote "
                'style="Margin: 0; border-left: 10px solid #B1B4B6;'
                "padding: 15px 0 0.1px 15px; font-size: 19px; line-height: 25px;"
                '">'
                '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">inset text</p>'
                "</blockquote>"
                "</div>"
            ),
        ],
        [
            notify_plain_text_email_markdown,
            ("\n\ninset text"),
        ],
    ),
)
def test_block_quote(markdown_function, expected):
    assert markdown_function("^ inset text") == expected


@pytest.mark.parametrize(
    "heading",
    (
        "# heading",
        "#heading",
    ),
)
@pytest.mark.parametrize(
    "markdown_function, expected",
    (
        [notify_letter_preview_markdown, "<h2>heading</h2>\n"],
        [
            notify_email_markdown,
            (
                '<h2 style="Margin: 0 0 15px 0; padding: 10px 0 0 0; font-size: 27px; '
                'line-height: 35px; font-weight: bold; color: #0B0C0C;">'
                "heading"
                "</h2>"
            ),
        ],
        [
            notify_plain_text_email_markdown,
            ("\n\n\nheading\n================================================================="),
        ],
    ),
)
def test_level_1_header(markdown_function, heading, expected):
    assert markdown_function(heading) == expected


@pytest.mark.parametrize(
    "markdown_function, expected",
    (
        [
            notify_letter_preview_markdown,
            "<p>Visit our [website](www.example.com/xyz).</p>",
        ],
        [
            notify_email_markdown,
            (
                '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">'
                'Visit our <a style="word-wrap: break-word; color: #1D70B8;" href="http://www.example.com/xyz">website</a>.</p>'
            ),
        ],
        [
            notify_plain_text_email_markdown,
            ("\n\nVisit our website: www.example.com/xyz."),
        ],
    ),
)
def test_external_link_without_http(markdown_function, expected):
    assert markdown_function("Visit our [website](www.example.com/xyz).") == (expected)


@pytest.mark.parametrize(
    "markdown_function, expected",
    (
        [
            notify_letter_preview_markdown,
            "<p>Visit our [website](https://www.example.com/xyz).</p>",
        ],
        [
            notify_email_markdown,
            (
                '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">'
                'Visit our <a style="word-wrap: break-word; color: #1D70B8;" href="https://www.example.com/xyz">website</a>.</p>'
            ),
        ],
        [
            notify_plain_text_email_markdown,
            ("\n\nVisit our website: https://www.example.com/xyz."),
        ],
    ),
)
def test_external_link_with_http(markdown_function, expected):
    assert markdown_function("Visit our [website](https://www.example.com/xyz).") == (expected)


@pytest.mark.parametrize(
    "url, expected_link_href",
    (
        (
            "mailto:unsubscribe@example.com",
            "mailto:unsubscribe%40example.com",
        ),
        (
            "mailto:unsubscribe%40example.com",
            "mailto:unsubscribe%40example.com",
        ),
        (
            r"file:///C:\Windows\system32\mspaint.exe",
            "file:///C:%5CWindows%5Csystem32%5Cmspaint.exe",
        ),
        (
            "tel:+44123",
            "tel:%2B44123",
        ),
        (
            "ftp://username:password@ftp.example.com/folder/",
            "ftp://username:password%40ftp.example.com/folder/",
        ),
    ),
)
def test_mailto_link_in_email_markdown_link(url, expected_link_href):
    paragraph = BeautifulSoup(
        notify_email_markdown(f"Unusual [link]({url})"),
        features="html.parser",
    )
    assert paragraph.select_one("a")["href"] == expected_link_href


@pytest.mark.parametrize(
    "markdown_function, expected",
    (
        [
            notify_letter_preview_markdown,
            '<p>Visit our [website](www.example.com/xyz "Link Title").</p>',
        ],
        [
            notify_email_markdown,
            (
                '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">'
                'Visit our <a style="word-wrap: break-word; color: #1D70B8;" href="http://www.example.com/xyz" '
                'title="Link Title">website</a>.</p>'
            ),
        ],
        [
            notify_plain_text_email_markdown,
            ("\n\nVisit our website (Link Title): www.example.com/xyz."),
        ],
    ),
)
def test_external_title_link_without_http(markdown_function, expected):
    assert markdown_function("Visit our [website](www.example.com/xyz 'Link Title').") == (expected)


@pytest.mark.parametrize(
    "markdown_function, expected",
    (
        [
            notify_letter_preview_markdown,
            '<p>Visit our [website](https://www.example.com/xyz "Link Title").</p>',
        ],
        [
            notify_email_markdown,
            (
                '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">'
                'Visit our <a style="word-wrap: break-word; color: #1D70B8;" href="https://www.example.com/xyz" '
                'title="Link Title">website</a>.</p>'
            ),
        ],
        [
            notify_plain_text_email_markdown,
            ("\n\nVisit our website (Link Title): https://www.example.com/xyz."),
        ],
    ),
)
def test_external_title_link_http(markdown_function, expected):
    assert markdown_function("Visit our [website](https://www.example.com/xyz 'Link Title').") == (expected)


@pytest.mark.parametrize(
    "markdown_function, expected",
    (
        [notify_letter_preview_markdown, "<p>heading</p>"],
        [
            notify_email_markdown,
            (
                '<h3 style="Margin: 0 0 15px 0; padding: 10px 0 0 0; font-size: 19px; '
                'line-height: 25px; font-weight: bold; color: #0B0C0C;">'
                "heading"
                "</h3>"
            ),
        ],
        [
            notify_plain_text_email_markdown,
            ("\n\n\nheading\n-----------------------------------------------------------------"),
        ],
    ),
)
def test_level_2_header(markdown_function, expected):
    assert markdown_function("## heading") == (expected)


@pytest.mark.parametrize(
    "markdown_function, expected",
    (
        [notify_letter_preview_markdown, "<p>inset text</p>"],
        [
            notify_email_markdown,
            '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">inset text</p>',
        ],
        [
            notify_plain_text_email_markdown,
            ("\n\ninset text"),
        ],
    ),
)
def test_level_3_header(markdown_function, expected):
    assert markdown_function("### inset text") == (expected)


@pytest.mark.parametrize(
    "markdown_function, expected",
    (
        [
            notify_letter_preview_markdown,
            ('<p>a</p><div class="page-break">&nbsp;</div><p>b</p>'),
        ],
        [
            notify_email_markdown,
            (
                '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">a</p>'
                '<hr style="border: 0; height: 1px; background: #B1B4B6; Margin: 30px 0 30px 0;">'
                '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">b</p>'
            ),
        ],
        [
            notify_plain_text_email_markdown,
            ("\n\na\n\n=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=\n\nb"),
        ],
    ),
)
def test_hrule(markdown_function, expected):
    assert markdown_function("a\n\n***\n\nb") == expected
    assert markdown_function("a\n\n---\n\nb") == expected


@pytest.mark.parametrize(
    "markdown_function, expected",
    (
        [
            notify_letter_preview_markdown,
            ("<ol>\n<li>one</li>\n<li>two</li>\n<li>three</li>\n</ol>\n"),
        ],
        [
            notify_email_markdown,
            (
                '<table role="presentation" style="padding: 0 0 20px 0;">'
                "<tr>"
                '<td style="font-family: Helvetica, Arial, sans-serif;">'
                '<ol style="Margin: 0 0 0 20px; padding: 0; list-style-type: decimal;">'
                '<li style="Margin: 5px 0 5px; padding: 0 0 0 5px; font-size: 19px;'
                'line-height: 25px; color: #0B0C0C;">one</li>'
                '<li style="Margin: 5px 0 5px; padding: 0 0 0 5px; font-size: 19px;'
                'line-height: 25px; color: #0B0C0C;">two</li>'
                '<li style="Margin: 5px 0 5px; padding: 0 0 0 5px; font-size: 19px;'
                'line-height: 25px; color: #0B0C0C;">three</li>'
                "</ol>"
                "</td>"
                "</tr>"
                "</table>"
            ),
        ],
        [
            notify_plain_text_email_markdown,
            ("\n\n1. one\n2. two\n3. three"),
        ],
    ),
)
def test_ordered_list(markdown_function, expected):
    assert markdown_function("1. one\n2. two\n3. three\n") == expected
    assert markdown_function("1.one\n2.two\n3.three\n") == expected


@pytest.mark.parametrize(
    "markdown",
    (
        ("*one\n*two\n*three\n"),  # no space
        ("* one\n* two\n* three\n"),  # single space
        ("*  one\n*  two\n*  three\n"),  # two spaces
        ("*  one\n*  two\n*  three\n"),  # tab
        ("- one\n- two\n- three\n"),  # dash as bullet
        pytest.param(("+ one\n+ two\n+ three\n"), marks=pytest.mark.xfail(raises=AssertionError)),  # plus as bullet
        ("• one\n• two\n• three\n"),  # bullet as bullet
    ),
)
@pytest.mark.parametrize(
    "markdown_function, expected",
    (
        [
            notify_letter_preview_markdown,
            ("<ul>\n<li>one</li>\n<li>two</li>\n<li>three</li>\n</ul>\n"),
        ],
        [
            notify_email_markdown,
            (
                '<table role="presentation" style="padding: 0 0 20px 0;">'
                "<tr>"
                '<td style="font-family: Helvetica, Arial, sans-serif;">'
                '<ul style="Margin: 0 0 0 20px; padding: 0; list-style-type: disc;">'
                '<li style="Margin: 5px 0 5px; padding: 0 0 0 5px; font-size: 19px;'
                'line-height: 25px; color: #0B0C0C;">one</li>'
                '<li style="Margin: 5px 0 5px; padding: 0 0 0 5px; font-size: 19px;'
                'line-height: 25px; color: #0B0C0C;">two</li>'
                '<li style="Margin: 5px 0 5px; padding: 0 0 0 5px; font-size: 19px;'
                'line-height: 25px; color: #0B0C0C;">three</li>'
                "</ul>"
                "</td>"
                "</tr>"
                "</table>"
            ),
        ],
        [
            notify_plain_text_email_markdown,
            ("\n\n• one\n• two\n• three"),
        ],
    ),
)
def test_unordered_list(markdown, markdown_function, expected):
    assert markdown_function(markdown) == expected


@pytest.mark.parametrize(
    "markdown_function, expected",
    (
        [
            notify_letter_preview_markdown,
            "<p>+ one</p><p>+ two</p><p>+ three</p>",
        ],
        [
            notify_email_markdown,
            (
                '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">+ one</p>'
                '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">+ two</p>'
                '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">+ three</p>'
            ),
        ],
        [
            notify_plain_text_email_markdown,
            ("\n\n+ one\n\n+ two\n\n+ three"),
        ],
    ),
)
def test_pluses_dont_render_as_lists(markdown_function, expected):
    assert markdown_function("+ one\n+ two\n+ three\n") == expected


@pytest.mark.parametrize(
    "markdown_function, expected",
    (
        [
            notify_letter_preview_markdown,
            ("<p>line one<br>line two</p><p>new paragraph</p>"),
        ],
        [
            notify_email_markdown,
            (
                '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">line one<br>'
                "line two</p>"
                '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">new paragraph</p>'
            ),
        ],
        [
            notify_plain_text_email_markdown,
            ("\n\nline one\nline two\n\nnew paragraph"),
        ],
    ),
)
def test_paragraphs(markdown_function, expected):
    assert markdown_function("line one\nline two\n\nnew paragraph") == expected


@pytest.mark.parametrize(
    "markdown_function, expected",
    (
        [notify_letter_preview_markdown, ("<p>before</p><p>after</p>")],
        [
            notify_email_markdown,
            (
                '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">before</p>'
                '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">after</p>'
            ),
        ],
        [
            notify_plain_text_email_markdown,
            ("\n\nbefore\n\nafter"),
        ],
    ),
)
def test_multiple_newlines_get_truncated(markdown_function, expected):
    assert markdown_function("before\n\n\n\n\n\nafter") == expected


@pytest.mark.parametrize(
    "markdown_function",
    (
        notify_letter_preview_markdown,
        notify_email_markdown,
        notify_plain_text_email_markdown,
    ),
)
def test_table(markdown_function):
    assert markdown_function("col | col\n----|----\nval | val\n") == ("")


@pytest.mark.parametrize(
    "markdown_function, link, expected",
    (
        [
            notify_letter_preview_markdown,
            "http://example.com",
            "<p><strong data-original-protocol='http://'>example.com</strong></p>",
        ],
        [
            notify_email_markdown,
            "http://example.com",
            (
                '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">'
                '<a style="word-wrap: break-word; color: #1D70B8;" href="http://example.com">http://example.com</a>'
                "</p>"
            ),
        ],
        [
            notify_email_markdown,
            """https://example.com"onclick="alert('hi')""",
            (
                '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">'
                '<a style="word-wrap: break-word; color: #1D70B8;" '
                'href="https://example.com%22onclick=%22alert%28%27hi">'
                'https://example.com"onclick="alert(\'hi'
                "</a>')"
                "</p>"
            ),
        ],
        [
            notify_plain_text_email_markdown,
            "http://example.com",
            ("\n\nhttp://example.com"),
        ],
    ),
)
def test_autolink(markdown_function, link, expected):
    assert markdown_function(link) == expected


@pytest.mark.parametrize(
    "markdown_function, expected",
    (
        [notify_letter_preview_markdown, "<p>variable called `thing`</p>"],
        [
            notify_email_markdown,
            (
                '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">'
                "variable called `thing`"
                "</p>"
            ),
        ],
        [
            notify_plain_text_email_markdown,
            "\n\nvariable called `thing`",
        ],
    ),
)
def test_codespan(markdown_function, expected):
    assert markdown_function("variable called `thing`") == expected


@pytest.mark.parametrize(
    "markdown_function, expected",
    (
        [notify_letter_preview_markdown, "<p>something **important**</p>"],
        [
            notify_email_markdown,
            (
                '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">'
                "something **important**"
                "</p>"
            ),
        ],
        [
            notify_plain_text_email_markdown,
            "\n\nsomething **important**",
        ],
    ),
)
def test_double_emphasis(markdown_function, expected):
    assert markdown_function("something **important**") == expected


@pytest.mark.parametrize(
    "markdown_function, text, expected",
    (
        [
            notify_letter_preview_markdown,
            "something *important*",
            "<p>something *important*</p>",
        ],
        [
            notify_email_markdown,
            "something *important*",
            (
                '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">'
                "something *important*"
                "</p>"
            ),
        ],
        [
            notify_plain_text_email_markdown,
            "something *important*",
            "\n\nsomething *important*",
        ],
        [
            notify_plain_text_email_markdown,
            "something _important_",
            "\n\nsomething _important_",
        ],
        [
            notify_plain_text_email_markdown,
            "before*after",
            "\n\nbefore*after",
        ],
        [
            notify_plain_text_email_markdown,
            "before_after",
            "\n\nbefore_after",
        ],
    ),
)
def test_emphasis(markdown_function, text, expected):
    assert markdown_function(text) == expected


@pytest.mark.parametrize(
    "markdown_function, expected",
    (
        [
            notify_email_markdown,
            '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">foo ****** bar</p>',
        ],
        [
            notify_plain_text_email_markdown,
            "\n\nfoo ****** bar",
        ],
    ),
)
def test_nested_emphasis(markdown_function, expected):
    assert markdown_function("foo ****** bar") == expected


@pytest.mark.parametrize(
    "markdown_function",
    (
        notify_letter_preview_markdown,
        notify_email_markdown,
        notify_plain_text_email_markdown,
    ),
)
def test_image(markdown_function):
    assert markdown_function("![alt text](http://example.com/image.png)") == ("")


@pytest.mark.parametrize(
    "markdown_function, expected",
    (
        [
            notify_letter_preview_markdown,
            ("<p>[Example](http://example.com)</p>"),
        ],
        [
            notify_email_markdown,
            (
                '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; '
                'color: #0B0C0C;">'
                '<a style="word-wrap: break-word; color: #1D70B8;" href="http://example.com">Example</a>'
                "</p>"
            ),
        ],
        [
            notify_plain_text_email_markdown,
            ("\n\nExample: http://example.com"),
        ],
    ),
)
def test_link(markdown_function, expected):
    assert markdown_function("[Example](http://example.com)") == expected


@pytest.mark.parametrize(
    "markdown_function, expected",
    (
        [
            notify_letter_preview_markdown,
            ('<p>[Example](http://example.com "An example URL")</p>'),
        ],
        [
            notify_email_markdown,
            (
                '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; '
                'color: #0B0C0C;">'
                '<a style="word-wrap: break-word; color: #1D70B8;" href="http://example.com" title="An example URL">'
                "Example"
                "</a>"
                "</p>"
            ),
        ],
        [
            notify_plain_text_email_markdown,
            ("\n\nExample (An example URL): http://example.com"),
        ],
    ),
)
def test_link_with_title(markdown_function, expected):
    assert markdown_function('[Example](http://example.com "An example URL")') == expected


def test_letter_qr_code():
    expected_qr_code = '<p><div class=\'qrcode\'><svg viewBox="0 0 25 25"><path stroke="#000" d="M0 0.5h7m1 0h8m2 0h7m🛳️🐦🥴25 1h1m5 0h1m1 0h1m1 0h1m1 0h5m1 0h1m5 0h1m🛳️🐦🥴25 1h1m1 0h3m1 0h1m1 0h1m3 0h1m2 0h1m2 0h1m1 0h3m1 0h1m🛳️🐦🥴25 1h1m1 0h3m1 0h1m1 0h2m1 0h1m6 0h1m1 0h3m1 0h1m🛳️🐦🥴25 1h1m1 0h3m1 0h1m1 0h5m1 0h2m2 0h1m1 0h3m1 0h1m🛳️🐦🥴25 1h1m5 0h1m3 0h1m4 0h2m1 0h1m5 0h1m🛳️🐦🥴25 1h7m1 0h1m1 0h1m1 0h1m1 0h1m1 0h1m1 0h7m🛳️🐦🥴17 1h1m2 0h3m🛳️🐦🥴13 1h2m1 0h1m1 0h2m1 0h1m1 0h2m1 0h1m1 0h1m1 0h1m1 0h5m🛳️🐦🥴25 1h3m5 0h1m1 0h2m1 0h1m2 0h3m5 0h1m🛳️🐦🥴25 1h1m1 0h1m3 0h7m1 0h1m1 0h1m1 0h1m1 0h1m1 0h3m🛳️🐦🥴25 1h2m1 0h1m1 0h1m1 0h1m3 0h3m2 0h1m2 0h2m2 0h1m🛳️🐦🥴24 1h4m2 0h1m2 0h1m4 0h6m1 0h1m1 0h2m🛳️🐦🥴23 1h1m2 0h1m2 0h2m1 0h1m1 0h1m3 0h2m2 0h1m2 0h1m🛳️🐦🥴25 1h1m1 0h1m1 0h1m1 0h3m1 0h1m2 0h2m2 0h1m1 0h2m1 0h3m🛳️🐦🥴24 1h2m4 0h1m1 0h2m2 0h1m1 0h2m4 0h1m1 0h1m🛳️🐦🥴24 1h1m4 0h2m3 0h1m1 0h1m1 0h1m1 0h6m🛳️🐦🥴14 1h3m1 0h1m2 0h2m3 0h5m🛳️🐦🥴25 1h7m1 0h2m2 0h1m2 0h2m1 0h1m1 0h1m2 0h2m🛳️🐦🥴25 1h1m5 0h1m2 0h2m3 0h1m1 0h1m3 0h2m2 0h1m🛳️🐦🥴25 1h1m1 0h3m1 0h1m1 0h3m2 0h1m2 0h5m3 0h1m🛳️🐦🥴25 1h1m1 0h3m1 0h1m2 0h1m1 0h1m1 0h3m3 0h2m1 0h1m🛳️🐦🥴23 1h1m1 0h3m1 0h1m1 0h1m1 0h1m1 0h2m1 0h1m1 0h1m1 0h3m2 0h1m🛳️🐦🥴25 1h1m5 0h1m1 0h1m2 0h1m1 0h5m2 0h2m1 0h1m🛳️🐦🥴24 1h7m3 0h2m2 0h3m1 0h2m3 0h2"/></svg></div></p>'  # noqa

    assert notify_letter_preview_markdown('qr:http://example.com"') == expected_qr_code


def test_letter_qr_code_works_with_extra_whitespace():
    expected_qr_code_start = "<p><div class='qrcode'><svg viewBox=\"0 0 25 25\">"
    assert notify_letter_preview_markdown(' qr : http://example.com"').startswith(expected_qr_code_start)


@pytest.mark.parametrize(
    "content, mock, expected_data",
    (
        (
            "qr: http://example.com",
            "notifications_utils.markdown.qr_code_as_svg",
            "http://example.com",
        ),
        (
            'qr: http://example.com?foo=<span class="placeholder">&#40;&#40;bar&#41;&#41;</span>',
            "notifications_utils.markdown.qr_code_placeholder",
            'http://example.com?foo=<span class="placeholder">&#40;&#40;bar&#41;&#41;</span>',
        ),
        (
            "qr: arbitrary data not a URL",
            "notifications_utils.markdown.qr_code_as_svg",
            "arbitrary data not a URL",
        ),
        (
            "qr: www.gov.uk/search?q=foo&r=bar",
            "notifications_utils.markdown.qr_code_as_svg",
            "www.gov.uk/search?q=foo&r=bar",
        ),
        (
            "qr: www.gov.uk/search?q=hello!@#$%^&*<>[]()\"'world",
            "notifications_utils.markdown.qr_code_as_svg",
            "www.gov.uk/search?q=hello!@#$%^&*<>[]()\"'world",
        ),
        (
            "qr: www.gov.uk/search?q=hello world",
            "notifications_utils.markdown.qr_code_as_svg",
            "www.gov.uk/search?q=hello world",
        ),
        (
            "qr: www.gov.uk/search?q=hello-world",
            "notifications_utils.markdown.qr_code_as_svg",
            "www.gov.uk/search?q=hello-world",
        ),
        (
            "qr: www.gov.uk/search?q=user@example.com",
            "notifications_utils.markdown.qr_code_as_svg",
            "www.gov.uk/search?q=user@example.com",
        ),
    ),
)
def test_letter_qr_code_only_passes_through_url(
    mocker,
    content,
    mock,
    expected_data,
):
    mock_render = mocker.patch(mock)
    notify_letter_preview_markdown(content)

    mock_render.assert_called_once_with(expected_data)


@pytest.mark.parametrize(
    "content, data, expected_data",
    (
        # This is the officially-supported syntax
        (
            "qr: ((data))",
            {"data": "https://www.example.com"},
            "https://www.example.com",
        ),
        ("qr: static", {}, "static"),
        (
            "qr: prefix https://www.google.com suffix",
            {},
            "prefix https://www.google.com suffix",
        ),
        (
            "qr: prefix ((data))",
            {"data": "https://www.example.com"},
            "prefix https://www.example.com",
        ),
        #
        # This is an old syntax which we don’t support, so we make sure it doesn't render broken QR codes
        ("[qr](((data)))", {"data": "https://www.example.com"}, None),
        ("[qr](static)", {}, None),
        ("[qr](prefix https://www.google.com suffix)", {}, None),
        ("[qr](prefix ((data)))", {"data": "https://www.example.com"}, None),
    ),
)
def test_qr_code_validator_gets_expected_data(mocker, content, data, expected_data):
    mock_render = mocker.patch("notifications_utils.markdown.NotifyLetterMarkdownValidatingRenderer._render_qr_data")

    Take(Field(content, data, html="escape")).then(notify_letter_qrcode_validator)
    if expected_data:
        assert mock_render.call_args_list == [mocker.call(expected_data)]
    else:
        assert mock_render.call_args_list == []


@pytest.mark.parametrize(
    "markdown_function, expected",
    (
        [notify_letter_preview_markdown, "<p>~~Strike~~</p>"],
        [
            notify_email_markdown,
            '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">~~Strike~~</p>',
        ],
        [notify_plain_text_email_markdown, "\n\n~~Strike~~"],
    ),
)
def test_strikethrough(markdown_function, expected):
    assert markdown_function("~~Strike~~") == expected


@pytest.mark.parametrize(
    "content, data, expected_html",
    [
        (
            "This is an escaped heading: \n ((var::make_safe))",
            {"var": "# This is heading 1"},
            '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">This is an escaped heading:<br> # This is heading 1</p>',  # noqa: E501
        ),
        (
            "This is an unescaped heading: \n ((var))",
            {"var": "# This is heading 1"},
            '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">This is an unescaped heading: </p><h2 style="Margin: 0 0 15px 0; padding: 10px 0 0 0; font-size: 27px; line-height: 35px; font-weight: bold; color: #0B0C0C;">This is heading 1</h2>',  # noqa: E501
        ),
    ],
)
def test_unsafe_placeholders_are_escaped_correctly(content, data, expected_html):
    assert notify_email_markdown(str(Field(content, data))) == expected_html


def test_footnotes():
    # Can’t work out how to test this
    pass
