import pytest
from flask import Markup

from notifications_utils.formatters import (
    escape_html,
    formatted_list,
    make_quotes_smart,
    normalise_whitespace,
    notify_email_markdown,
    notify_letter_preview_markdown,
    notify_plain_text_email_markdown,
    remove_smart_quotes_from_email_addresses,
    remove_whitespace_before_punctuation,
    replace_hyphens_with_en_dashes,
    sms_encode,
    strip_and_remove_obscure_whitespace,
    strip_unsupported_characters,
    strip_whitespace,
    unlink_govuk_escaped,
)
from notifications_utils.template import (
    HTMLEmailTemplate,
    PlainTextEmailTemplate,
    SMSMessageTemplate,
    SMSPreviewTemplate,
)


@pytest.mark.parametrize(
    "url", [
        "http://example.com",
        "http://www.gov.uk/",
        "https://www.gov.uk/",
        "http://service.gov.uk",
        "http://service.gov.uk/blah.ext?q=a%20b%20c&order=desc#fragment",
        pytest.param("http://service.gov.uk/blah.ext?q=one two three", marks=pytest.mark.xfail),
    ]
)
def test_makes_links_out_of_URLs(url):
    link = '<a style="word-wrap: break-word; color: #1D70B8;" href="{}">{}</a>'.format(url, url)
    assert (notify_email_markdown(url) == (
        '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">'
        '{}'
        '</p>'
    ).format(link))


@pytest.mark.parametrize('input, output', [
    (
        (
            'this is some text with a link http://example.com in the middle'
        ),
        (
            'this is some text with a link '
            '<a style="word-wrap: break-word; color: #1D70B8;" href="http://example.com">http://example.com</a>'
            ' in the middle'
        ),
    ),
    (
        (
            'this link is in brackets (http://example.com)'
        ),
        (
            'this link is in brackets '
            '(<a style="word-wrap: break-word; color: #1D70B8;" href="http://example.com">http://example.com</a>)'
        ),
    )
])
def test_makes_links_out_of_URLs_in_context(input, output):
    assert notify_email_markdown(input) == (
        '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">'
        '{}'
        '</p>'
    ).format(output)


@pytest.mark.parametrize(
    "url", [
        "example.com",
        "www.example.com",
        "ftp://example.com",
        "test@example.com",
        "mailto:test@example.com",
        "<a href=\"https://example.com\">Example</a>",
    ]
)
def test_doesnt_make_links_out_of_invalid_urls(url):
    assert notify_email_markdown(url) == (
        '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">'
        '{}'
        '</p>'
    ).format(url)


def test_handles_placeholders_in_urls():
    assert notify_email_markdown(
        "http://example.com/?token=<span class='placeholder'>((token))</span>&key=1"
    ) == (
        '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">'
        '<a style="word-wrap: break-word; color: #1D70B8;" href="http://example.com/?token=">'
        'http://example.com/?token='
        '</a>'
        '<span class=\'placeholder\'>((token))</span>&amp;key=1'
        '</p>'
    )


@pytest.mark.parametrize(
    "url, expected_html, expected_html_in_template", [
        (
            """https://example.com"onclick="alert('hi')""",
            """<a style="word-wrap: break-word; color: #1D70B8;" href="https://example.com%22onclick=%22alert%28%27hi">https://example.com"onclick="alert('hi</a>')""",  # noqa
            """<a style="word-wrap: break-word; color: #1D70B8;" href="https://example.com%22onclick=%22alert%28%27hi">https://example.com"onclick="alert('hi</a>‘)""",  # noqa
        ),
        (
            """https://example.com"style='text-decoration:blink'""",
            """<a style="word-wrap: break-word; color: #1D70B8;" href="https://example.com%22style=%27text-decoration:blink">https://example.com"style='text-decoration:blink</a>'""",  # noqa
            """<a style="word-wrap: break-word; color: #1D70B8;" href="https://example.com%22style=%27text-decoration:blink">https://example.com"style='text-decoration:blink</a>’""",  # noqa
        ),
    ]
)
def test_URLs_get_escaped(url, expected_html, expected_html_in_template):
    assert notify_email_markdown(url) == (
        '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">'
        '{}'
        '</p>'
    ).format(expected_html)
    assert expected_html_in_template in str(HTMLEmailTemplate({
        'content': url, 'subject': '', 'template_type': 'email',
    }))


@pytest.mark.parametrize(
    "url, expected_html", [
        (
            """https://example.com"onclick="alert('hi')""",
            """<a style="word-wrap: break-word; color: #1D70B8;" href="https://example.com%22onclick=%22alert%28%27hi">https://example.com"onclick="alert('hi</a>')""",  # noqa
        ),
        (
            """https://example.com"style='text-decoration:blink'""",
            """<a style="word-wrap: break-word; color: #1D70B8;" href="https://example.com%22style=%27text-decoration:blink">https://example.com"style='text-decoration:blink</a>'""",  # noqa
        ),
    ]
)
def test_URLs_get_escaped_in_sms(url, expected_html):
    assert expected_html in str(SMSPreviewTemplate({'content': url, 'template_type': 'sms'}))


def test_HTML_template_has_URLs_replaced_with_links():
    assert (
        '<a style="word-wrap: break-word; color: #1D70B8;" href="https://service.example.com/accept_invite/a1b2c3d4">'
        'https://service.example.com/accept_invite/a1b2c3d4'
        '</a>'
    ) in str(HTMLEmailTemplate({'content': (
        'You’ve been invited to a service. Click this link:\n'
        'https://service.example.com/accept_invite/a1b2c3d4\n'
        '\n'
        'Thanks\n'
    ), 'subject': '', 'template_type': 'email'}))


@pytest.mark.parametrize('markdown_function, expected_output', [
    (notify_email_markdown, (
        '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">'
        '<a style="word-wrap: break-word; color: #1D70B8;" href="https://example.com">'
        'https://example.com'
        '</a>'
        '</p>'
        '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">'
        'Next paragraph'
        '</p>'
    )),
    (notify_plain_text_email_markdown, (
        '\n'
        '\nhttps://example.com'
        '\n'
        '\nNext paragraph'
    )),
])
def test_preserves_whitespace_when_making_links(
    markdown_function, expected_output
):
    assert markdown_function(
        'https://example.com\n'
        '\n'
        'Next paragraph'
    ) == expected_output


def test_escaping_govuk_in_email_templates():
    template_content = "GOV.UK"
    expected = "GOV.\u200BUK"
    assert unlink_govuk_escaped(template_content) == expected
    template_json = {'content': template_content, 'subject': '', 'template_type': 'email'}
    assert expected in str(PlainTextEmailTemplate(template_json))
    assert expected in str(HTMLEmailTemplate(template_json))


@pytest.mark.parametrize(
    "template_content,expected", [
        # Cases that we add the breaking space
        ("GOV.UK", "GOV.\u200BUK"),
        ("gov.uk", "gov.\u200Buk"),
        ("content with space infront GOV.UK", "content with space infront GOV.\u200BUK"),
        ("content with tab infront\tGOV.UK", "content with tab infront\tGOV.\u200BUK"),
        ("content with newline infront\nGOV.UK", "content with newline infront\nGOV.\u200BUK"),
        ("*GOV.UK", "*GOV.\u200BUK"),
        ("#GOV.UK", "#GOV.\u200BUK"),
        ("^GOV.UK", "^GOV.\u200BUK"),
        (" #GOV.UK", " #GOV.\u200BUK"),
        ("GOV.UK with CONTENT after", "GOV.\u200BUK with CONTENT after"),
        ("#GOV.UK with CONTENT after", "#GOV.\u200BUK with CONTENT after"),

        # Cases that we don't add the breaking space
        ("https://gov.uk", "https://gov.uk"),
        ("https://www.gov.uk", "https://www.gov.uk"),
        ("www.gov.uk", "www.gov.uk"),
        ("WWW.GOV.UK", "WWW.GOV.UK"),
        ("WWW.GOV.UK.", "WWW.GOV.UK."),
        ("https://www.gov.uk/?utm_source=gov.uk", "https://www.gov.uk/?utm_source=gov.uk"),
        ("mygov.uk", "mygov.uk"),
        ("www.this-site-is-not-gov.uk", "www.this-site-is-not-gov.uk"),
        ("www.gov.uk?websites=bbc.co.uk;gov.uk;nsh.scot", "www.gov.uk?websites=bbc.co.uk;gov.uk;nsh.scot"),
        ("reply to: xxxx@xxx.gov.uk", "reply to: xxxx@xxx.gov.uk"),
        ("southwark.gov.uk", "southwark.gov.uk"),
        ("data.gov.uk", "data.gov.uk"),
        ("gov.uk/foo", "gov.uk/foo"),
        ("*GOV.UK/foo", "*GOV.UK/foo"),
        ("#GOV.UK/foo", "#GOV.UK/foo"),
        ("^GOV.UK/foo", "^GOV.UK/foo"),
        ("gov.uk#departments-and-policy", "gov.uk#departments-and-policy"),

        # Cases that we know currently aren't supported by our regex and have a non breaking space added when they
        # shouldn't however, we accept the fact that our regex isn't perfect as we think the chance of a user using a
        # URL like this in their content is very small.
        # We document these edge cases here
        pytest.param("gov.uk.com", "gov.uk.com", marks=pytest.mark.xfail),
        pytest.param("gov.ukandi.com", "gov.ukandi.com", marks=pytest.mark.xfail),
        pytest.param("gov.uks", "gov.uks", marks=pytest.mark.xfail),
    ]
)
def test_unlink_govuk_escaped(template_content, expected):
    assert unlink_govuk_escaped(template_content) == expected


@pytest.mark.parametrize(
    "prefix, body, expected", [
        ("a", "b", "a: b"),
        (None, "b", "b"),
    ]
)
def test_sms_message_adds_prefix(prefix, body, expected):
    template = SMSMessageTemplate({'content': body, 'template_type': 'sms'})
    template.prefix = prefix
    template.sender = None
    assert str(template) == expected


def test_sms_preview_adds_newlines():
    template = SMSPreviewTemplate({'content': """
        the
        quick

        brown fox
    """, "template_type": "sms"})
    template.prefix = None
    template.sender = None
    assert '<br>' in str(template)


@pytest.mark.parametrize(
    'markdown_function, expected',
    (
        [
            notify_letter_preview_markdown,
            'print("hello")'
        ],
        [
            notify_email_markdown,
            'print("hello")'
        ],
        [
            notify_plain_text_email_markdown,
            'print("hello")'
        ],
    )
)
def test_block_code(markdown_function, expected):
    assert markdown_function('```\nprint("hello")\n```') == expected


@pytest.mark.parametrize('markdown_function, expected', (
    [
        notify_letter_preview_markdown,
        (
            '<p>inset text</p>'
        )
    ],
    [
        notify_email_markdown,
        (
            '<blockquote '
            'style="Margin: 0 0 20px 0; border-left: 10px solid #B1B4B6;'
            'padding: 15px 0 0.1px 15px; font-size: 19px; line-height: 25px;'
            '">'
            '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">inset text</p>'
            '</blockquote>'
        )
    ],
    [
        notify_plain_text_email_markdown,
        (
            '\n'
            '\ninset text'
        ),
    ],
))
def test_block_quote(markdown_function, expected):
    assert markdown_function('^ inset text') == expected


@pytest.mark.parametrize('heading', (
    '# heading',
    '#heading',
))
@pytest.mark.parametrize(
    'markdown_function, expected',
    (
        [
            notify_letter_preview_markdown,
            '<h2>heading</h2>\n'
        ],
        [
            notify_email_markdown,
            (
                '<h2 style="Margin: 0 0 20px 0; padding: 0; font-size: 27px; '
                'line-height: 35px; font-weight: bold; color: #0B0C0C;">'
                'heading'
                '</h2>'
            )
        ],
        [
            notify_plain_text_email_markdown,
            (
                '\n'
                '\n'
                '\nheading'
                '\n-----------------------------------------------------------------'
            ),
        ],
    )
)
def test_level_1_header(markdown_function, heading, expected):
    assert markdown_function(heading) == expected


@pytest.mark.parametrize('markdown_function, expected', (
    [
        notify_letter_preview_markdown,
        '<p>inset text</p>'
    ],
    [
        notify_email_markdown,
        '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">inset text</p>'
    ],
    [
        notify_plain_text_email_markdown,
        (
            '\n'
            '\ninset text'
        ),
    ],
))
def test_level_2_header(markdown_function, expected):
    assert markdown_function('## inset text') == (expected)


@pytest.mark.parametrize('markdown_function, expected', (
    [
        notify_letter_preview_markdown,
        (
            '<p>a</p>'
            '<div class="page-break">&nbsp;</div>'
            '<p>b</p>'
        )
    ],
    [
        notify_email_markdown,
        (
            '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">a</p>'
            '<hr style="border: 0; height: 1px; background: #B1B4B6; Margin: 30px 0 30px 0;">'
            '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">b</p>'
        )
    ],
    [
        notify_plain_text_email_markdown,
        (
            '\n'
            '\na'
            '\n'
            '\n================================================================='
            '\n'
            '\nb'
        ),
    ],
))
def test_hrule(markdown_function, expected):
    assert markdown_function('a\n\n***\n\nb') == expected
    assert markdown_function('a\n\n---\n\nb') == expected


@pytest.mark.parametrize('markdown_function, expected', (
    [
        notify_letter_preview_markdown,
        (
            '<ol>\n'
            '<li>one</li>\n'
            '<li>two</li>\n'
            '<li>three</li>\n'
            '</ol>\n'
        )
    ],
    [
        notify_email_markdown,
        (
            '<table role="presentation" style="padding: 0 0 20px 0;">'
            '<tr>'
            '<td style="font-family: Helvetica, Arial, sans-serif;">'
            '<ol style="Margin: 0 0 0 20px; padding: 0; list-style-type: decimal;">'
            '<li style="Margin: 5px 0 5px; padding: 0 0 0 5px; font-size: 19px;'
            'line-height: 25px; color: #0B0C0C;">one</li>'
            '<li style="Margin: 5px 0 5px; padding: 0 0 0 5px; font-size: 19px;'
            'line-height: 25px; color: #0B0C0C;">two</li>'
            '<li style="Margin: 5px 0 5px; padding: 0 0 0 5px; font-size: 19px;'
            'line-height: 25px; color: #0B0C0C;">three</li>'
            '</ol>'
            '</td>'
            '</tr>'
            '</table>'
        )
    ],
    [
        notify_plain_text_email_markdown,
        (
            '\n'
            '\n1. one'
            '\n2. two'
            '\n3. three'
        ),
    ],
))
def test_ordered_list(markdown_function, expected):
    assert markdown_function(
        '1. one\n'
        '2. two\n'
        '3. three\n'
    ) == expected
    assert markdown_function(
        '1.one\n'
        '2.two\n'
        '3.three\n'
    ) == expected


@pytest.mark.parametrize('markdown', (
    (  # no space
        '*one\n'
        '*two\n'
        '*three\n'
    ),
    (  # single space
        '* one\n'
        '* two\n'
        '* three\n'
    ),
    (  # two spaces
        '*  one\n'
        '*  two\n'
        '*  three\n'
    ),
    (  # tab
        '*  one\n'
        '*  two\n'
        '*  three\n'
    ),
    (  # dash as bullet
        '- one\n'
        '- two\n'
        '- three\n'
    ),
    pytest.param((  # plus as bullet
        '+ one\n'
        '+ two\n'
        '+ three\n'
    ), marks=pytest.mark.xfail(raises=AssertionError)),
    (  # bullet as bullet
        '• one\n'
        '• two\n'
        '• three\n'
    ),
))
@pytest.mark.parametrize('markdown_function, expected', (
    [
        notify_letter_preview_markdown,
        (
            '<ul>\n'
            '<li>one</li>\n'
            '<li>two</li>\n'
            '<li>three</li>\n'
            '</ul>\n'
        )
    ],
    [
        notify_email_markdown,
        (
            '<table role="presentation" style="padding: 0 0 20px 0;">'
            '<tr>'
            '<td style="font-family: Helvetica, Arial, sans-serif;">'
            '<ul style="Margin: 0 0 0 20px; padding: 0; list-style-type: disc;">'
            '<li style="Margin: 5px 0 5px; padding: 0 0 0 5px; font-size: 19px;'
            'line-height: 25px; color: #0B0C0C;">one</li>'
            '<li style="Margin: 5px 0 5px; padding: 0 0 0 5px; font-size: 19px;'
            'line-height: 25px; color: #0B0C0C;">two</li>'
            '<li style="Margin: 5px 0 5px; padding: 0 0 0 5px; font-size: 19px;'
            'line-height: 25px; color: #0B0C0C;">three</li>'
            '</ul>'
            '</td>'
            '</tr>'
            '</table>'
        )
    ],
    [
        notify_plain_text_email_markdown,
        (
            '\n'
            '\n• one'
            '\n• two'
            '\n• three'
        ),
    ],
))
def test_unordered_list(markdown, markdown_function, expected):
    assert markdown_function(markdown) == expected


@pytest.mark.parametrize('markdown_function, expected', (
    [
        notify_letter_preview_markdown,
        '<p>+ one</p><p>+ two</p><p>+ three</p>',
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
        (
            '\n\n+ one'
            '\n\n+ two'
            '\n\n+ three'
        ),
    ],
))
def test_pluses_dont_render_as_lists(markdown_function, expected):
    assert markdown_function(
        '+ one\n'
        '+ two\n'
        '+ three\n'
    ) == expected


@pytest.mark.parametrize('markdown_function, expected', (
    [
        notify_letter_preview_markdown,
        (
            '<p>'
            'line one<br>'
            'line two'
            '</p>'
            '<p>'
            'new paragraph'
            '</p>'
        )
    ],
    [
        notify_email_markdown,
        (
            '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">line one<br />'
            'line two</p>'
            '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">new paragraph</p>'
        )
    ],
    [
        notify_plain_text_email_markdown,
        (
            '\n'
            '\nline one'
            '\nline two'
            '\n'
            '\nnew paragraph'
        ),
    ],
))
def test_paragraphs(markdown_function, expected):
    assert markdown_function(
        'line one\n'
        'line two\n'
        '\n'
        'new paragraph'
    ) == expected


@pytest.mark.parametrize('markdown_function, expected', (
    [
        notify_letter_preview_markdown,
        (
            '<p>before</p>'
            '<p>after</p>'
        )
    ],
    [
        notify_email_markdown,
        (
            '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">before</p>'
            '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">after</p>'
        )
    ],
    [
        notify_plain_text_email_markdown,
        (
            '\n'
            '\nbefore'
            '\n'
            '\nafter'
        ),
    ],
))
def test_multiple_newlines_get_truncated(markdown_function, expected):
    assert markdown_function(
        'before\n\n\n\n\n\nafter'
    ) == expected


@pytest.mark.parametrize('markdown_function', (
    notify_letter_preview_markdown, notify_email_markdown, notify_plain_text_email_markdown
))
def test_table(markdown_function):
    assert markdown_function(
        'col | col\n'
        '----|----\n'
        'val | val\n'
    ) == (
        ''
    )


@pytest.mark.parametrize('markdown_function, link, expected', (
    [
        notify_letter_preview_markdown,
        'http://example.com',
        '<p><strong>example.com</strong></p>'
    ],
    [
        notify_email_markdown,
        'http://example.com',
        (
            '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">'
            '<a style="word-wrap: break-word; color: #1D70B8;" href="http://example.com">http://example.com</a>'
            '</p>'
        )
    ],
    [
        notify_email_markdown,
        """https://example.com"onclick="alert('hi')""",
        (
            '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">'
            '<a style="word-wrap: break-word; color: #1D70B8;" href="https://example.com%22onclick=%22alert%28%27hi">'
            'https://example.com"onclick="alert(\'hi'
            '</a>\')'
            '</p>'
        )
    ],
    [
        notify_plain_text_email_markdown,
        'http://example.com',
        (
            '\n'
            '\nhttp://example.com'
        ),
    ],
))
def test_autolink(markdown_function, link, expected):
    assert markdown_function(link) == expected


@pytest.mark.parametrize('markdown_function, expected', (
    [
        notify_letter_preview_markdown,
        '<p>variable called `thing`</p>'
    ],
    [
        notify_email_markdown,
        '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">variable called `thing`</p>'
    ],
    [
        notify_plain_text_email_markdown,
        '\n\nvariable called `thing`',
    ],
))
def test_codespan(markdown_function, expected):
    assert markdown_function(
        'variable called `thing`'
    ) == expected


@pytest.mark.parametrize('markdown_function, expected', (
    [
        notify_letter_preview_markdown,
        '<p>something **important**</p>'
    ],
    [
        notify_email_markdown,
        '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">something **important**</p>'
    ],
    [
        notify_plain_text_email_markdown,
        '\n\nsomething **important**',
    ],
))
def test_double_emphasis(markdown_function, expected):
    assert markdown_function(
        'something **important**'
    ) == expected


@pytest.mark.parametrize('markdown_function, text, expected', (
    [
        notify_letter_preview_markdown,
        'something *important*',
        '<p>something *important*</p>'
    ],
    [
        notify_email_markdown,
        'something *important*',
        '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">something *important*</p>'
    ],
    [
        notify_plain_text_email_markdown,
        'something *important*',
        '\n\nsomething *important*',
    ],
    [
        notify_plain_text_email_markdown,
        'something _important_',
        '\n\nsomething _important_',
    ],
    [
        notify_plain_text_email_markdown,
        'before*after',
        '\n\nbefore*after',
    ],
    [
        notify_plain_text_email_markdown,
        'before_after',
        '\n\nbefore_after',
    ],
))
def test_emphasis(markdown_function, text, expected):
    assert markdown_function(text) == expected


@pytest.mark.parametrize('markdown_function, expected', (
    [
        notify_email_markdown,
        '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">foo ****** bar</p>'
    ],
    [
        notify_plain_text_email_markdown,
        '\n\nfoo ****** bar',
    ],
))
def test_nested_emphasis(markdown_function, expected):
    assert markdown_function(
        'foo ****** bar'
    ) == expected


@pytest.mark.parametrize('markdown_function', (
    notify_letter_preview_markdown, notify_email_markdown, notify_plain_text_email_markdown
))
def test_image(markdown_function):
    assert markdown_function(
        '![alt text](http://example.com/image.png)'
    ) == (
        ''
    )


@pytest.mark.parametrize('markdown_function, expected', (
    [
        notify_letter_preview_markdown,
        (
            '<p>Example: <strong>example.com</strong></p>'
        )
    ],
    [
        notify_email_markdown,
        (
            '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; '
            'color: #0B0C0C;">'
            '<a style="word-wrap: break-word; color: #1D70B8;" href="http://example.com">Example</a>'
            '</p>'
        )
    ],
    [
        notify_plain_text_email_markdown,
        (
            '\n'
            '\nExample: http://example.com'
        ),
    ],
))
def test_link(markdown_function, expected):
    assert markdown_function(
        '[Example](http://example.com)'
    ) == expected


@pytest.mark.parametrize('markdown_function, expected', (
    [
        notify_letter_preview_markdown,
        (
            '<p>Example: <strong>example.com</strong></p>'
        )
    ],
    [
        notify_email_markdown,
        (
            '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; '
            'color: #0B0C0C;">'
            '<a style="word-wrap: break-word; color: #1D70B8;" href="http://example.com" title="An example URL">'
            'Example'
            '</a>'
            '</p>'
        )
    ],
    [
        notify_plain_text_email_markdown,
        (
            '\n'
            '\nExample (An example URL): http://example.com'
        ),
    ],
))
def test_link_with_title(markdown_function, expected):
    assert markdown_function(
        '[Example](http://example.com "An example URL")'
    ) == expected


@pytest.mark.parametrize('markdown_function, expected', (
    [
        notify_letter_preview_markdown,
        '<p>~~Strike~~</p>'
    ],
    [
        notify_email_markdown,
        '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">~~Strike~~</p>'
    ],
    [
        notify_plain_text_email_markdown,
        '\n\n~~Strike~~'
    ],
))
def test_strikethrough(markdown_function, expected):
    assert markdown_function('~~Strike~~') == expected


def test_footnotes():
    # Can’t work out how to test this
    pass


def test_sms_encode(mocker):
    sanitise_mock = mocker.patch('notifications_utils.formatters.SanitiseSMS')
    assert sms_encode('foo') == sanitise_mock.encode.return_value
    sanitise_mock.encode.assert_called_once_with('foo')


@pytest.mark.parametrize('items, kwargs, expected_output', [
    ([1], {}, '‘1’'),
    ([1, 2], {}, '‘1’ and ‘2’'),
    ([1, 2, 3], {}, '‘1’, ‘2’ and ‘3’'),
    ([1, 2, 3], {'prefix': 'foo', 'prefix_plural': 'bar'}, 'bar ‘1’, ‘2’ and ‘3’'),
    ([1], {'prefix': 'foo', 'prefix_plural': 'bar'}, 'foo ‘1’'),
    ([1, 2, 3], {'before_each': 'a', 'after_each': 'b'}, 'a1b, a2b and a3b'),
    ([1, 2, 3], {'conjunction': 'foo'}, '‘1’, ‘2’ foo ‘3’'),
    (['&'], {'before_each': '<i>', 'after_each': '</i>'}, '<i>&amp;</i>'),
    ([1, 2, 3], {'before_each': '<i>', 'after_each': '</i>'}, '<i>1</i>, <i>2</i> and <i>3</i>'),
])
def test_formatted_list(items, kwargs, expected_output):
    assert formatted_list(items, **kwargs) == expected_output


def test_formatted_list_returns_markup():
    assert isinstance(formatted_list([0]), Markup)


def test_bleach_doesnt_try_to_make_valid_html_before_cleaning():
    assert escape_html(
        "<to cancel daily cat facts reply 'cancel'>"
    ) == (
        "&lt;to cancel daily cat facts reply 'cancel'&gt;"
    )


@pytest.mark.parametrize('content, expected_escaped', (
    ('&?a;', '&amp;?a;'),
    ('&>a;', '&amp;&gt;a;'),
    ('&*a;', '&amp;*a;'),
    ('&a?;', '&amp;a?;'),
    ('&x?xa;', '&amp;x?xa;'),
    # We need to be careful that query arguments don’t get turned into entities
    ('&timestamp=&times;', '&amp;timestamp=×'),
    ('&times=1,2,3', '&amp;times=1,2,3'),
    # &minus; should have a trailing semicolon according to the HTML5
    # spec but &micro doesn’t need one
    ('2&minus;1', '2−1'),
    ('200&micro;g', '200µg'),
    # …we ignore it when it’s ambiguous
    ('2&minus1', '2&amp;minus1'),
    ('200&microg', '200&amp;microg'),
    # …we still ignore when there’s a space afterwards
    ('2 &minus 1', '2 &amp;minus 1'),
    ('200&micro g', '200&amp;micro g'),
    # Things which aren’t real entities are ignored, not removed
    ('This &isnotarealentity;', 'This &amp;isnotarealentity;'),
    # We let users use &nbsp; for backwards compatibility
    ('Before&nbsp;after', 'Before&nbsp;after'),
    # We let users use &amp; because it’s often pasted in URLs
    ('?a=1&amp;b=2', '?a=1&amp;b=2'),
    # We let users use &lpar; and &rpar; because otherwise it’s
    # impossible to put brackets in the body of conditional placeholders
    ('((var??&lpar;in brackets&rpar;))', '((var??&lpar;in brackets&rpar;))'),
))
def test_escaping_html_entities(
    content,
    expected_escaped,
):
    assert escape_html(content) == expected_escaped


@pytest.mark.parametrize('dirty, clean', [
    (
        'Hello ((name)) ,\n\nThis is a message',
        'Hello ((name)),\n\nThis is a message'
    ),
    (
        'Hello Jo ,\n\nThis is a message',
        'Hello Jo,\n\nThis is a message'
    ),
    (
        '\n   \t    , word',
        '\n, word',
    ),
])
def test_removing_whitespace_before_commas(dirty, clean):
    assert remove_whitespace_before_punctuation(dirty) == clean


@pytest.mark.parametrize('dirty, clean', [
    (
        'Hello ((name)) .\n\nThis is a message',
        'Hello ((name)).\n\nThis is a message'
    ),
    (
        'Hello Jo .\n\nThis is a message',
        'Hello Jo.\n\nThis is a message'
    ),
    (
        '\n   \t    . word',
        '\n. word',
    ),
])
def test_removing_whitespace_before_full_stops(dirty, clean):
    assert remove_whitespace_before_punctuation(dirty) == clean


@pytest.mark.parametrize('dumb, smart', [
    (
        """And I said, "what about breakfast at Tiffany's"?""",
        """And I said, “what about breakfast at Tiffany’s”?""",
    ),
    (
        """
            <a href="http://example.com?q='foo'">http://example.com?q='foo'</a>
        """,
        """
            <a href="http://example.com?q='foo'">http://example.com?q='foo'</a>
        """,
    ),
])
def test_smart_quotes(dumb, smart):
    assert make_quotes_smart(dumb) == smart


@pytest.mark.parametrize('nasty, nice', [
    (
        (
            'The en dash - always with spaces in running text when, as '
            'discussed in this section, indicating a parenthesis or '
            'pause - and the spaced em dash both have a certain '
            'technical advantage over the unspaced em dash. '
        ),
        (
            'The en dash \u2013 always with spaces in running text when, as '
            'discussed in this section, indicating a parenthesis or '
            'pause \u2013 and the spaced em dash both have a certain '
            'technical advantage over the unspaced em dash. '
        ),
    ),
    (
        'double -- dash',
        'double \u2013 dash',
    ),
    (
        'triple --- dash',
        'triple \u2013 dash',
    ),
    (
        'quadruple ---- dash',
        'quadruple ---- dash',
    ),
    (
        'em — dash',
        'em – dash',
    ),
    (
        'already\u0020–\u0020correct',  # \u0020 is a normal space character
        'already\u0020–\u0020correct',
    ),
    (
        '2004-2008',
        '2004-2008',  # no replacement
    ),
])
def test_en_dashes(nasty, nice):
    assert replace_hyphens_with_en_dashes(nasty) == nice


def test_unicode_dash_lookup():
    en_dash_replacement_sequence = '\u0020\u2013'
    hyphen = '-'
    en_dash = '–'
    space = ' '
    non_breaking_space = ' '
    assert en_dash_replacement_sequence == space + en_dash
    assert non_breaking_space not in en_dash_replacement_sequence
    assert hyphen not in en_dash_replacement_sequence


@pytest.mark.parametrize('value', [
    'bar',
    ' bar ',
    """
        \t    bar
    """,
    ' \u180E\u200B \u200C bar \u200D \u2060\uFEFF ',
])
def test_strip_whitespace(value):
    assert strip_whitespace(value) == 'bar'


@pytest.mark.parametrize('value', [
    'notifications-email',
    '  \tnotifications-email \x0c ',
    '\rn\u200Coti\u200Dfi\u200Bcati\u2060ons-\u180Eemai\uFEFFl\uFEFF',
])
def test_strip_and_remove_obscure_whitespace(value):
    assert strip_and_remove_obscure_whitespace(value) == 'notifications-email'


def test_strip_and_remove_obscure_whitespace_only_removes_normal_whitespace_from_ends():
    sentence = '   words \n over multiple lines with \ttabs\t   '
    assert strip_and_remove_obscure_whitespace(sentence) == 'words \n over multiple lines with \ttabs'


def test_remove_smart_quotes_from_email_addresses():
    assert remove_smart_quotes_from_email_addresses("""
        line one’s quote
        first.o’last@example.com is someone’s email address
        line ‘three’
    """) == ("""
        line one’s quote
        first.o'last@example.com is someone’s email address
        line ‘three’
    """)


def test_strip_unsupported_characters():
    assert strip_unsupported_characters("line one\u2028line two") == ("line oneline two")


def test_normalise_whitespace():
    assert normalise_whitespace('\u200C Your tax   is\ndue\n\n') == 'Your tax is due'
