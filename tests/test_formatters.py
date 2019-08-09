import pytest
from flask import Markup

from notifications_utils.formatters import (
    unlink_govuk_escaped,
    notify_email_markdown,
    notify_letter_preview_markdown,
    notify_plain_text_email_markdown,
    sms_encode,
    formatted_list,
    strip_dvla_markup,
    strip_pipes,
    escape_html,
    remove_whitespace_before_punctuation,
    make_quotes_smart,
    replace_hyphens_with_en_dashes,
    tweak_dvla_list_markup,
    nl2li,
    strip_whitespace,
    strip_and_remove_obscure_whitespace,
    remove_smart_quotes_from_email_addresses,
    strip_unsupported_characters,
)
from notifications_utils.template import (
    HTMLEmailTemplate,
    PlainTextEmailTemplate,
    SMSMessageTemplate,
    SMSPreviewTemplate
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
    link = '<a style="word-wrap: break-word; color: #005ea5;" href="{}">{}</a>'.format(url, url)
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
            '<a style="word-wrap: break-word; color: #005ea5;" href="http://example.com">http://example.com</a>'
            ' in the middle'
        ),
    ),
    (
        (
            'this link is in brackets (http://example.com)'
        ),
        (
            'this link is in brackets '
            '(<a style="word-wrap: break-word; color: #005ea5;" href="http://example.com">http://example.com</a>)'
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
        '<a style="word-wrap: break-word; color: #005ea5;" href="http://example.com/?token=">'
        'http://example.com/?token='
        '</a>'
        '<span class=\'placeholder\'>((token))</span>&amp;key=1'
        '</p>'
    )


@pytest.mark.parametrize(
    "url, expected_html, expected_html_in_template", [
        (
            """https://example.com"onclick="alert('hi')""",
            """<a style="word-wrap: break-word; color: #005ea5;" href="https://example.com%22onclick=%22alert%28%27hi">https://example.com"onclick="alert('hi</a>')""",  # noqa
            """<a style="word-wrap: break-word; color: #005ea5;" href="https://example.com%22onclick=%22alert%28%27hi">https://example.com"onclick="alert('hi</a>‘)""",  # noqa
        ),
        (
            """https://example.com"style='text-decoration:blink'""",
            """<a style="word-wrap: break-word; color: #005ea5;" href="https://example.com%22style=%27text-decoration:blink">https://example.com"style='text-decoration:blink</a>'""",  # noqa
            """<a style="word-wrap: break-word; color: #005ea5;" href="https://example.com%22style=%27text-decoration:blink">https://example.com"style='text-decoration:blink</a>’""",  # noqa
        ),
    ]
)
def test_URLs_get_escaped(url, expected_html, expected_html_in_template):
    assert notify_email_markdown(url) == (
        '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">'
        '{}'
        '</p>'
    ).format(expected_html)
    assert expected_html_in_template in str(HTMLEmailTemplate({'content': url, 'subject': ''}))


def test_HTML_template_has_URLs_replaced_with_links():
    assert (
        '<a style="word-wrap: break-word; color: #005ea5;" href="https://service.example.com/accept_invite/a1b2c3d4">'
        'https://service.example.com/accept_invite/a1b2c3d4'
        '</a>'
    ) in str(HTMLEmailTemplate({'content': (
        'You’ve been invited to a service. Click this link:\n'
        'https://service.example.com/accept_invite/a1b2c3d4\n'
        '\n'
        'Thanks\n'
    ), 'subject': ''}))


@pytest.mark.parametrize('markdown_function, expected_output', [
    (notify_email_markdown, (
        '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">'
        '<a style="word-wrap: break-word; color: #005ea5;" href="https://example.com">'
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


@pytest.mark.parametrize(
    "template_content,expected", [
        ("gov.uk", u"gov.\u200Buk"),
        ("GOV.UK", u"GOV.\u200BUK"),
        ("Gov.uk", u"Gov.\u200Buk"),
        ("https://gov.uk", "https://gov.uk"),
        ("https://www.gov.uk", "https://www.gov.uk"),
        ("www.gov.uk", "www.gov.uk"),
        ("gov.uk/register-to-vote", "gov.uk/register-to-vote"),
        ("gov.uk?q=", "gov.uk?q=")
    ]
)
def test_escaping_govuk_in_email_templates(template_content, expected):
    assert unlink_govuk_escaped(template_content) == expected
    assert expected in str(PlainTextEmailTemplate({'content': template_content, 'subject': ''}))
    assert expected in str(HTMLEmailTemplate({'content': template_content, 'subject': ''}))


@pytest.mark.parametrize(
    "prefix, body, expected", [
        ("a", "b", "a: b"),
        (None, "b", "b"),
    ]
)
def test_sms_message_adds_prefix(prefix, body, expected):
    template = SMSMessageTemplate({'content': body})
    template.prefix = prefix
    template.sender = None
    assert str(template) == expected


def test_sms_preview_adds_newlines():
    template = SMSPreviewTemplate({'content': """
        the
        quick

        brown fox
    """})
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
            'style="Margin: 0 0 20px 0; border-left: 10px solid #BFC1C3;'
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
            '<hr style="border: 0; height: 1px; background: #BFC1C3; Margin: 30px 0 30px 0;">'
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
            '<a style="word-wrap: break-word; color: #005ea5;" href="http://example.com">http://example.com</a>'
            '</p>'
        )
    ],
    [
        notify_email_markdown,
        """https://example.com"onclick="alert('hi')""",
        (
            '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">'
            '<a style="word-wrap: break-word; color: #005ea5;" href="https://example.com%22onclick=%22alert%28%27hi">'
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
        '<p>variable called thing</p>'
    ],
    [
        notify_email_markdown,
        '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">variable called thing</p>'
    ],
    [
        notify_plain_text_email_markdown,
        '\n\nvariable called thing',
    ],
))
def test_codespan(markdown_function, expected):
    assert markdown_function(
        'variable called `thing`'
    ) == expected


@pytest.mark.parametrize('markdown_function, expected', (
    [
        notify_letter_preview_markdown,
        '<p>something important</p>'
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


@pytest.mark.parametrize('markdown_function, expected', (
    [
        notify_letter_preview_markdown,
        '<p>something important</p>'
    ],
    [
        notify_email_markdown,
        '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">something *important*</p>'
    ],
    [
        notify_plain_text_email_markdown,
        '\n\nsomething *important*',
    ],
))
def test_emphasis(markdown_function, expected):
    assert markdown_function(
        'something *important*'
    ) == expected


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
            '<a style="word-wrap: break-word; color: #005ea5;" href="http://example.com">Example</a>'
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
            '<a style="word-wrap: break-word; color: #005ea5;" href="http://example.com" title="An example URL">'
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
        '<p>Strike</p>'
    ],
    [
        notify_email_markdown,
        '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">Strike</p>'
    ],
    [
        notify_plain_text_email_markdown,
        '\n\nStrike'
    ],
))
def test_strikethrough(markdown_function, expected):
    assert markdown_function('~~Strike~~') == expected


def test_footnotes():
    # Can’t work out how to test this
    pass


def test_sms_encode():
    assert sms_encode('aàā…') == 'aàa...'


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


def test_removing_dvla_markup():
    assert strip_dvla_markup(
        (
            'some words & some more <words>'
            '<cr><h1><h2><p><normal><op><np><bul><tab>'
            '<CR><H1><H2><P><NORMAL><OP><NP><BUL><TAB>'
            '<tAb>'
        )
    ) == 'some words & some more <words>'


def test_removing_pipes():
    assert strip_pipes('|a|b|c') == 'abc'


def test_bleach_doesnt_try_to_make_valid_html_before_cleaning():
    assert escape_html(
        "<to cancel daily cat facts reply 'cancel'>"
    ) == (
        "&lt;to cancel daily cat facts reply 'cancel'&gt;"
    )


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


@pytest.mark.parametrize('markup, expected_fixed', [
    (
        'a',
        'a',
    ),
    (
        'before<p><cr><p><cr>after',
        'before<p><cr>after',
    ),
    (
        'before<cr><cr><np>after',
        'before<cr><np>after',
    ),
    (
        'before{}<np>after'.format('<cr>' * 4),
        'before{}<np>after'.format('<cr>' * 3),
    ),
])
def test_tweaking_dvla_list_markup(markup, expected_fixed):
    assert tweak_dvla_list_markup(markup) == expected_fixed


def test_make_list_from_linebreaks():
    assert nl2li(
        'a\n'
        'b\n'
        'c\n'
    ) == (
        '<ul>'
        '<li>a</li>'
        '<li>b</li>'
        '<li>c</li>'
        '</ul>'
    )


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
