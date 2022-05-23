import re
import string
from html import _replace_charref, escape

import bleach
import mistune
import smartypants
from markupsafe import Markup

from notifications_utils.markdown import (
    NotifyEmailMarkdownRenderer,
    NotifyEmailPreheaderMarkdownRenderer,
    NotifyLetterMarkdownPreviewRenderer,
    NotifyPlainTextEmailMarkdownRenderer,
    create_sanitised_html_for_url,
)
from notifications_utils.sanitise_text import SanitiseSMS

from . import email_with_smart_quotes_regex

OBSCURE_ZERO_WIDTH_WHITESPACE = (
    '\u180E'  # Mongolian vowel separator
    '\u200B'  # zero width space
    '\u200C'  # zero width non-joiner
    '\u200D'  # zero width joiner
    '\u2060'  # word joiner
    '\uFEFF'  # zero width non-breaking space
)

OBSCURE_FULL_WIDTH_WHITESPACE = (
    '\u00A0'  # non breaking space
)

ALL_WHITESPACE = string.whitespace + OBSCURE_ZERO_WIDTH_WHITESPACE + OBSCURE_FULL_WIDTH_WHITESPACE

govuk_not_a_link = re.compile(
    r'(^|\s)(#|\*|\^)?(GOV)\.(UK)(?!\/|\?|#)',
    re.IGNORECASE
)

smartypants.tags_to_skip = smartypants.tags_to_skip + ['a']

whitespace_before_punctuation = re.compile(r'[ \t]+([,\.])')

hyphens_surrounded_by_spaces = re.compile(r'\s+[-–—]{1,3}\s+')  # check three different unicode hyphens

multiple_newlines = re.compile(r'((\n)\2{2,})')

HTML_ENTITY_MAPPING = (
    ('&nbsp;', "👾🐦🥴"),
    ('&amp;', "➕🐦🥴"),
    ('&lpar;', "◀️🐦🥴"),
    ('&rpar;', "▶️🐦🥴"),
)

# The Mistune URL regex only matches URLs at the start of a string,
# using `^`, so we slice that off and recompile
url = re.compile(mistune.InlineGrammar.url.pattern[1:])

more_than_two_newlines_in_a_row = re.compile(r'\n{3,}')


def unlink_govuk_escaped(message):
    return re.sub(
        govuk_not_a_link,
        r'\1\2\3' + '.\u200B' + r'\4',  # Unicode zero-width space
        message
    )


def nl2br(value):
    return re.sub(r'\n|\r', '<br>', value.strip())


def add_prefix(body, prefix=None):
    if prefix:
        return "{}: {}".format(prefix.strip(), body)
    return body


def autolink_sms(body):
    return url.sub(
        lambda match: create_sanitised_html_for_url(match.group(1)),
        body,
    )


def prepend_subject(body, subject):
    return '# {}\n\n{}'.format(subject, body)


def sms_encode(content):
    return SanitiseSMS.encode(content)


def strip_html(value):
    return bleach.clean(value, tags=[], strip=True)


"""
Re-implements html._charref but makes trailing semicolons non-optional
"""
_charref = re.compile(
    r'&(#[0-9]+;'
    r'|#[xX][0-9a-fA-F]+;'
    r'|[^\t\n\f <&#;]{1,32};)'
)


def unescape_strict(s):
    """
    Re-implements html.unescape to use our own definition of `_charref`
    """
    if '&' not in s:
        return s
    return _charref.sub(_replace_charref, s)


def escape_html(value):
    if not value:
        return value
    value = str(value)

    for entity, temporary_replacement in HTML_ENTITY_MAPPING:
        value = value.replace(entity, temporary_replacement)

    value = escape(unescape_strict(value), quote=False)

    for entity, temporary_replacement in HTML_ENTITY_MAPPING:
        value = value.replace(temporary_replacement, entity)

    return value


def url_encode_full_stops(value):
    return value.replace('.', '%2E')


def unescaped_formatted_list(
    items,
    conjunction='and',
    before_each='‘',
    after_each='’',
    separator=', ',
    prefix='',
    prefix_plural=''
):
    if prefix:
        prefix += ' '
    if prefix_plural:
        prefix_plural += ' '

    if len(items) == 1:
        return '{prefix}{before_each}{items[0]}{after_each}'.format(**locals())
    elif items:
        formatted_items = ['{}{}{}'.format(before_each, item, after_each) for item in items]

        first_items = separator.join(formatted_items[:-1])
        last_item = formatted_items[-1]
        return (
            '{prefix_plural}{first_items} {conjunction} {last_item}'
        ).format(**locals())


def formatted_list(
    items,
    conjunction='and',
    before_each='‘',
    after_each='’',
    separator=', ',
    prefix='',
    prefix_plural=''
):
    return Markup(
        unescaped_formatted_list(
            [escape_html(x) for x in items],
            conjunction,
            before_each,
            after_each,
            separator,
            prefix,
            prefix_plural
        )
    )


def remove_whitespace_before_punctuation(value):
    return re.sub(
        whitespace_before_punctuation,
        lambda match: match.group(1),
        value
    )


def make_quotes_smart(value):
    return smartypants.smartypants(
        value,
        smartypants.Attr.q | smartypants.Attr.u
    )


def replace_hyphens_with_en_dashes(value):
    return re.sub(
        hyphens_surrounded_by_spaces,
        (
            ' '       # space
            '\u2013'  # en dash
            ' '       # space
        ),
        value,
    )


def replace_hyphens_with_non_breaking_hyphens(value):
    return value.replace(
        '-',
        '\u2011',  # non-breaking hyphen
    )


def normalise_whitespace_and_newlines(value):
    return '\n'.join(get_lines_with_normalised_whitespace(value))


def get_lines_with_normalised_whitespace(value):
    return [
        normalise_whitespace(line) for line in value.splitlines()
    ]


def normalise_whitespace(value):
    # leading and trailing whitespace removed
    # inner whitespace with width becomes a single space
    # inner whitespace with zero width is removed
    # multiple space characters next to each other become just a single space character
    for character in OBSCURE_FULL_WIDTH_WHITESPACE:
        value = value.replace(character, ' ')

    for character in OBSCURE_ZERO_WIDTH_WHITESPACE:
        value = value.replace(character, '')

    return ' '.join(value.split())


def normalise_multiple_newlines(value):
    return more_than_two_newlines_in_a_row.sub('\n\n', value)


def strip_leading_whitespace(value):
    return value.lstrip()


def add_trailing_newline(value):
    return '{}\n'.format(value)


def remove_smart_quotes_from_email_addresses(value):

    def remove_smart_quotes(match):
        value = match.group(0)
        for character in '‘’':
            value = value.replace(character, "'")
        return value

    return email_with_smart_quotes_regex.sub(
        remove_smart_quotes,
        value,
    )


def strip_all_whitespace(value, extra_characters=''):
    # Removes from the beginning and end of the string all whitespace characters and `extra_characters`
    if value is not None and hasattr(value, 'strip'):
        return value.strip(ALL_WHITESPACE + extra_characters)
    return value


def strip_and_remove_obscure_whitespace(value):
    if value == '':
        # Return early to avoid making multiple, slow calls to
        # str.replace on an empty string
        return ''

    for character in OBSCURE_ZERO_WIDTH_WHITESPACE + OBSCURE_FULL_WIDTH_WHITESPACE:
        value = value.replace(character, '')

    return value.strip(string.whitespace)


def remove_whitespace(value):
    # Removes ALL whitespace, not just the obscure characters we normaly remove
    for character in ALL_WHITESPACE:
        value = value.replace(character, '')

    return value


def strip_unsupported_characters(value):
    return value.replace('\u2028', '')


notify_email_markdown = mistune.Markdown(
    renderer=NotifyEmailMarkdownRenderer(),
    hard_wrap=True,
    use_xhtml=False,
)
notify_plain_text_email_markdown = mistune.Markdown(
    renderer=NotifyPlainTextEmailMarkdownRenderer(),
    hard_wrap=True,
)
notify_email_preheader_markdown = mistune.Markdown(
    renderer=NotifyEmailPreheaderMarkdownRenderer(),
    hard_wrap=True,
)
notify_letter_preview_markdown = mistune.Markdown(
    renderer=NotifyLetterMarkdownPreviewRenderer(),
    hard_wrap=True,
    use_xhtml=False,
)
