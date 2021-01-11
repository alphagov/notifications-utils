import re
import string
import urllib
from html import _replace_charref, escape
from itertools import count

import bleach
import mistune
import smartypants
from flask import Markup
from orderedset import OrderedSet

from notifications_utils.sanitise_text import SanitiseSMS

from . import email_with_smart_quotes_regex

LINK_STYLE = 'word-wrap: break-word; color: #1D70B8;'

OBSCURE_WHITESPACE = (
    '\u180E'  # Mongolian vowel separator
    '\u200B'  # zero width space
    '\u200C'  # zero width non-joiner
    '\u200D'  # zero width joiner
    '\u2060'  # word joiner
    '\u00A0'  # non breaking space
    '\uFEFF'  # zero width non-breaking space
)


mistune._block_quote_leading_pattern = re.compile(r'^ *\^ ?', flags=re.M)
mistune.BlockGrammar.block_quote = re.compile(r'^( *\^[^\n]+(\n[^\n]+)*\n*)+')
mistune.BlockGrammar.list_block = re.compile(
    r'^( *)([•*-]|\d+\.)[\s\S]+?'
    r'(?:'
    r'\n+(?=\1?(?:[-*_] *){3,}(?:\n+|$))'  # hrule
    r'|\n+(?=%s)'  # def links
    r'|\n+(?=%s)'  # def footnotes
    r'|\n{2,}'
    r'(?! )'
    r'(?!\1(?:[•*-]|\d+\.) )\n*'
    r'|'
    r'\s*$)' % (
        mistune._pure_pattern(mistune.BlockGrammar.def_links),
        mistune._pure_pattern(mistune.BlockGrammar.def_footnotes),
    )
)
mistune.BlockGrammar.list_item = re.compile(
    r'^(( *)(?:[•*-]|\d+\.)[^\n]*'
    r'(?:\n(?!\2(?:[•*-]|\d+\.))[^\n]*)*)',
    flags=re.M
)
mistune.BlockGrammar.list_bullet = re.compile(r'^ *(?:[•*-]|\d+\.)')
mistune.InlineGrammar.url = re.compile(r'''^(https?:\/\/[^\s<]+[^<.,:"')\]\s])''')

mistune.InlineLexer.default_rules = list(
    OrderedSet(mistune.InlineLexer.default_rules) - set((
        'emphasis',
        'double_emphasis',
        'strikethrough',
        'code',
    ))
)
mistune.InlineLexer.inline_html_rules = list(
    set(mistune.InlineLexer.inline_html_rules) - set((
        'emphasis',
        'double_emphasis',
        'strikethrough',
        'code',
    ))
)

govuk_not_a_link = re.compile(
    r'(^|\s)(#|\*|\^)?(GOV)\.(UK)(?!\/|\?|#)',
    re.IGNORECASE
)

smartypants.tags_to_skip = smartypants.tags_to_skip + ['a']

whitespace_before_punctuation = re.compile(r'[ \t]+([,\.])')

hyphens_surrounded_by_spaces = re.compile(r'\s+[-–—]{1,3}\s+')  # check three different unicode hyphens

multiple_newlines = re.compile(r'((\n)\2{2,})')

MAGIC_SEQUENCE = "🇬🇧🐦✉️"

magic_sequence_regex = re.compile(MAGIC_SEQUENCE)

HTML_ENTITY_MAPPING = (
    ('&nbsp;', "👾🐦🥴"),
    ('&amp;', "➕🐦🥴"),
    ('&lpar;', "◀️🐦🥴"),
    ('&rpar;', "▶️🐦🥴"),
)

# The Mistune URL regex only matches URLs at the start of a string,
# using `^`, so we slice that off and recompile
url = re.compile(mistune.InlineGrammar.url.pattern[1:])

multiple_spaces_in_a_row = re.compile(r'\s{2,}')

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


def create_sanitised_html_for_url(link):
    """
    takes a link and returns an a tag to that link.  does the quote/unquote dance to ensure that " quotes are escaped
    correctly to prevent xss

    input: `http://foo.com/"bar"?x=1#2`
    output: `<a style=... href="http://foo.com/%22bar%22?x=1#2">http://foo.com/"bar"?x=1#2</a>`
    """
    return '<a style="{}" href="{}">{}</a>'.format(
        LINK_STYLE,
        urllib.parse.quote(
            urllib.parse.unquote(link),
            safe=':/?#=&;'
        ),
        link
    )


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
    return '\n'.join(normalise_lines(value))


def normalise_lines(value):
    return [
        normalise_line(line) for line in value.splitlines()
    ]


def normalise_line(line):
    return multiple_spaces_in_a_row.sub(
        ' ',
        strip_and_remove_obscure_whitespace(line),
    )


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


def strip_whitespace(value, extra_characters=''):
    if value is not None and hasattr(value, 'strip'):
        return value.strip(string.whitespace + OBSCURE_WHITESPACE + extra_characters)
    return value


def strip_and_remove_obscure_whitespace(value):
    for character in OBSCURE_WHITESPACE:
        value = value.replace(character, '')

    return value.strip(string.whitespace)


def remove_whitespace(value):
    for character in string.whitespace + OBSCURE_WHITESPACE:
        value = value.replace(character, '')

    return value


def strip_unsupported_characters(value):
    return value.replace('\u2028', '')


def normalise_whitespace(value):
    # leading and trailing whitespace removed, all inner whitespace becomes a single space
    return ' '.join(strip_and_remove_obscure_whitespace(value).split())


class NotifyLetterMarkdownPreviewRenderer(mistune.Renderer):

    def block_code(self, code, language=None):
        return code

    def block_quote(self, text):
        return text

    def header(self, text, level, raw=None):
        if level == 1:
            return super().header(text, 2)
        return self.paragraph(text)

    def hrule(self):
        return '<div class="page-break">&nbsp;</div>'

    def paragraph(self, text):
        if text.strip():
            return '<p>{}</p>'.format(text)
        return ''

    def table(self, header, body):
        return ""

    def autolink(self, link, is_email=False):
        return '<strong>{}</strong>'.format(
            link.replace('http://', '').replace('https://', '')
        )

    def image(self, src, title, alt_text):
        return ""

    def linebreak(self):
        return "<br>"

    def newline(self):
        return self.linebreak()

    def list_item(self, text):
        return '<li>{}</li>\n'.format(text.strip())

    def link(self, link, title, content):
        return '{}: {}'.format(content, self.autolink(link))

    def footnote_ref(self, key, index):
        return ""

    def footnote_item(self, key, text):
        return text

    def footnotes(self, text):
        return text


class NotifyEmailMarkdownRenderer(NotifyLetterMarkdownPreviewRenderer):

    def header(self, text, level, raw=None):
        if level == 1:
            return (
                '<h2 style="Margin: 0 0 20px 0; padding: 0; '
                'font-size: 27px; line-height: 35px; font-weight: bold; color: #0B0C0C;">'
                '{}'
                '</h2>'
            ).format(
                text
            )
        return self.paragraph(text)

    def hrule(self):
        return (
            '<hr style="border: 0; height: 1px; background: #B1B4B6; Margin: 30px 0 30px 0;">'
        )

    def linebreak(self):
        return "<br />"

    def list(self, body, ordered=True):
        return (
            '<table role="presentation" style="padding: 0 0 20px 0;">'
            '<tr>'
            '<td style="font-family: Helvetica, Arial, sans-serif;">'
            '<ol style="Margin: 0 0 0 20px; padding: 0; list-style-type: decimal;">'
            '{}'
            '</ol>'
            '</td>'
            '</tr>'
            '</table>'
        ).format(
            body
        ) if ordered else (
            '<table role="presentation" style="padding: 0 0 20px 0;">'
            '<tr>'
            '<td style="font-family: Helvetica, Arial, sans-serif;">'
            '<ul style="Margin: 0 0 0 20px; padding: 0; list-style-type: disc;">'
            '{}'
            '</ul>'
            '</td>'
            '</tr>'
            '</table>'
        ).format(
            body
        )

    def list_item(self, text):
        return (
            '<li style="Margin: 5px 0 5px; padding: 0 0 0 5px; font-size: 19px;'
            'line-height: 25px; color: #0B0C0C;">'
            '{}'
            '</li>'
        ).format(
            text.strip()
        )

    def paragraph(self, text):
        if text.strip():
            return (
                '<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">{}</p>'
            ).format(
                text
            )
        return ""

    def block_quote(self, text):
        return (
            '<blockquote '
            'style="Margin: 0 0 20px 0; border-left: 10px solid #B1B4B6;'
            'padding: 15px 0 0.1px 15px; font-size: 19px; line-height: 25px;"'
            '>'
            '{}'
            '</blockquote>'
        ).format(
            text
        )

    def link(self, link, title, content):
        return (
            '<a style="{}"{}{}>{}</a>'
        ).format(
            LINK_STYLE,
            ' href="{}"'.format(link),
            ' title="{}"'.format(title) if title else "",
            content,
        )

    def autolink(self, link, is_email=False):
        if is_email:
            return link
        return create_sanitised_html_for_url(link)


class NotifyPlainTextEmailMarkdownRenderer(NotifyEmailMarkdownRenderer):

    COLUMN_WIDTH = 65

    def header(self, text, level, raw=None):
        if level == 1:
            return ''.join((
                self.linebreak() * 3,
                text,
                self.linebreak(),
                '-' * self.COLUMN_WIDTH,
            ))
        return self.paragraph(text)

    def hrule(self):
        return self.paragraph(
            '=' * self.COLUMN_WIDTH
        )

    def linebreak(self):
        return '\n'

    def list(self, body, ordered=True):

        def _get_list_marker():
            decimal = count(1)
            return lambda _: '{}.'.format(next(decimal)) if ordered else '•'

        return ''.join((
            self.linebreak(),
            re.sub(
                magic_sequence_regex,
                _get_list_marker(),
                body,
            ),
        ))

    def list_item(self, text):
        return ''.join((
            self.linebreak(),
            MAGIC_SEQUENCE,
            ' ',
            text.strip(),
        ))

    def paragraph(self, text):
        if text.strip():
            return ''.join((
                self.linebreak() * 2,
                text,
            ))
        return ""

    def block_quote(self, text):
        return text

    def link(self, link, title, content):
        return ''.join((
            content,
            ' ({})'.format(title) if title else '',
            ': ',
            link,
        ))

    def autolink(self, link, is_email=False):
        return link


class NotifyEmailPreheaderMarkdownRenderer(NotifyPlainTextEmailMarkdownRenderer):

    def header(self, text, level, raw=None):
        return self.paragraph(text)

    def hrule(self):
        return ''

    def link(self, link, title, content):
        return ''.join((
            content,
            ' ({})'.format(title) if title else '',
        ))


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
