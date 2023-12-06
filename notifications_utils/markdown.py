import itertools
import re
from itertools import count

import mistune
from ordered_set import OrderedSet

from notifications_utils import MAGIC_SEQUENCE, magic_sequence_regex
from notifications_utils.formatters import create_sanitised_html_for_url, replace_svg_dashes
from notifications_utils.qr_code import (
    QR_CODE_MAX_BYTES,
    QrCodeTooLong,
    paragraph_is_qr_code_markup_regex,
    qr_code_as_svg,
    qr_code_placeholder,
)

LINK_STYLE = "word-wrap: break-word; color: #1D70B8;"

mistune._block_quote_leading_pattern = re.compile(r"^ *\^ ?", flags=re.M)
mistune.BlockGrammar.block_quote = re.compile(r"^( *\^[^\n]+(\n[^\n]+)*\n*)+")
mistune.BlockGrammar.list_block = re.compile(
    r"^( *)([•*-]|\d+\.)[\s\S]+?"
    r"(?:"
    r"\n+(?=\1?(?:[-*_] *){3,}(?:\n+|$))"  # hrule
    r"|\n+(?=%s)"  # def links
    r"|\n+(?=%s)"  # def footnotes
    r"|\n{2,}"
    r"(?! )"
    r"(?!\1(?:[•*-]|\d+\.) )\n*"
    r"|"
    r"\s*$)"
    % (
        mistune._pure_pattern(mistune.BlockGrammar.def_links),
        mistune._pure_pattern(mistune.BlockGrammar.def_footnotes),
    )
)
mistune.BlockGrammar.list_item = re.compile(
    r"^(( *)(?:[•*-]|\d+\.)[^\n]*" r"(?:\n(?!\2(?:[•*-]|\d+\.))[^\n]*)*)", flags=re.M
)
mistune.BlockGrammar.list_bullet = re.compile(r"^ *(?:[•*-]|\d+\.)")
mistune.InlineGrammar.url = re.compile(r"""^(https?:\/\/[^\s<]+[^<.,:"')\]\s])""")

mistune.InlineLexer.default_rules = list(
    OrderedSet(mistune.InlineLexer.default_rules)
    - set(
        (
            "emphasis",
            "double_emphasis",
            "strikethrough",
            "code",
        )
    )
)
mistune.InlineLexer.inline_html_rules = list(
    set(mistune.InlineLexer.inline_html_rules)
    - set(
        (
            "emphasis",
            "double_emphasis",
            "strikethrough",
            "code",
        )
    )
)


def qr_code_contents_from_paragraph(text):
    if match := paragraph_is_qr_code_markup_regex.fullmatch(text):
        return match[1]


class NotifyLetterMarkdownPreviewRenderer(mistune.Renderer):
    def _render_qr_data(self, data):
        if "<span class='placeholder" in data or '<span class="placeholder' in data:
            placeholder = qr_code_placeholder(data)
            return replace_svg_dashes(placeholder)

        qr_data = qr_code_as_svg(data)
        return f"<div class='qrcode'>{replace_svg_dashes(qr_data)}</div>"

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
        if not text.strip():
            return ""

        if qr_code_contents := qr_code_contents_from_paragraph(text):
            # Restore http:// or https:// and strip out the <strong> tag that gets injected by
            # the `link`/`autolink` methods
            text = self._render_qr_data(
                re.sub(r"<strong data-original-protocol='(https?://|)'>(.*?)</strong>", r"\1\2", qr_code_contents)
            )

        return f"<p>{text}</p>"

    def table(self, header, body):
        return ""

    def autolink(self, link, is_email=False):
        proto_matcher = re.compile(r"^(https?://)")

        protocol = ""
        if match := proto_matcher.match(link):
            protocol = match.group(1)
            link = proto_matcher.sub("", link, 1)

        return f"<strong data-original-protocol='{protocol}'>{link}</strong>"

    def image(self, src, title, alt_text):
        return ""

    def linebreak(self):
        return "<br>"

    def newline(self):
        return self.linebreak()

    def list_item(self, text):
        return f"<li>{text.strip()}</li>\n"

    def link(self, link, title, content):
        if link.startswith("span class='placeholder") and link.endswith("</span"):
            link = f"<{link}>"

        if title:
            return f'[{content}]({link} "{title}")'

        return f"[{content}]({link})"

    def footnote_ref(self, key, index):
        return ""

    def footnote_item(self, key, text):
        return text

    def footnotes(self, text):
        return text


class NotifyLetterMarkdownValidatingRenderer(NotifyLetterMarkdownPreviewRenderer):
    """Renders letter markdown as normal, except validates QR code data does not exceed a maximum length."""

    def _render_qr_data(self, data):
        if (num_bytes := len(data.encode("utf8"))) > QR_CODE_MAX_BYTES:
            raise QrCodeTooLong(num_bytes=num_bytes, data=data)

        return data


class NotifyEmailMarkdownRenderer(NotifyLetterMarkdownPreviewRenderer):
    def header(self, text, level, raw=None):
        if level == 1:
            return (
                '<h2 style="Margin: 0 0 15px 0; padding: 10px 0 0 0; '
                'font-size: 27px; line-height: 35px; font-weight: bold; color: #0B0C0C;">'
                f"{text}"
                "</h2>"
            )
        if level == 2:
            return (
                '<h3 style="Margin: 0 0 15px 0; padding: 10px 0 0 0; '
                'font-size: 19px; line-height: 25px; font-weight: bold; color: #0B0C0C;">'
                f"{text}"
                "</h3>"
            )
        return self.paragraph(text)

    def hrule(self):
        return '<hr style="border: 0; height: 1px; background: #B1B4B6; Margin: 30px 0 30px 0;">'

    def linebreak(self):
        return "<br>"

    def list(self, body, ordered=True):
        return (
            (
                '<table role="presentation" style="padding: 0 0 20px 0;">'
                "<tr>"
                '<td style="font-family: Helvetica, Arial, sans-serif;">'
                '<ol style="Margin: 0 0 0 20px; padding: 0; list-style-type: decimal;">'
                f"{body}"
                "</ol>"
                "</td>"
                "</tr>"
                "</table>"
            )
            if ordered
            else (
                '<table role="presentation" style="padding: 0 0 20px 0;">'
                "<tr>"
                '<td style="font-family: Helvetica, Arial, sans-serif;">'
                '<ul style="Margin: 0 0 0 20px; padding: 0; list-style-type: disc;">'
                f"{body}"
                "</ul>"
                "</td>"
                "</tr>"
                "</table>"
            )
        )

    def list_item(self, text):
        return (
            '<li style="Margin: 5px 0 5px; padding: 0 0 0 5px; font-size: 19px;'
            'line-height: 25px; color: #0B0C0C;">'
            f"{text.strip()}"
            "</li>"
        )

    def paragraph(self, text):
        if text.strip():
            return f'<p style="Margin: 0 0 20px 0; font-size: 19px; line-height: 25px; color: #0B0C0C;">{text}</p>'
        return ""

    def block_quote(self, text):
        return (
            "<blockquote "
            'style="Margin: 0 0 20px 0; border-left: 10px solid #B1B4B6;'
            'padding: 15px 0 0.1px 15px; font-size: 19px; line-height: 25px;"'
            ">"
            f"{text}"
            "</blockquote>"
        )

    def link(self, link, title, content):
        if link.startswith("span class='placeholder") and link.endswith("</span"):
            link = f"<{link}>"
        if title:
            return f'<a style="{LINK_STYLE}" href="{link}" title="{title}">{content}</a>'
        return f'<a style="{LINK_STYLE}" href="{link}">{content}</a>'

    def autolink(self, link, is_email=False):
        if is_email:
            return link
        return create_sanitised_html_for_url(link, style=LINK_STYLE)


class NotifyPlainTextEmailMarkdownRenderer(NotifyEmailMarkdownRenderer):
    COLUMN_WIDTH = 65

    def header(self, text, level, raw=None):
        if level == 1:
            return "".join(
                (
                    self.linebreak() * 3,
                    text,
                    self.linebreak(),
                    "=" * self.COLUMN_WIDTH,
                )
            )
        elif level == 2:
            return "".join(
                (
                    self.linebreak() * 3,
                    text,
                    self.linebreak(),
                    "-" * self.COLUMN_WIDTH,
                )
            )
        return self.paragraph(text)

    def hrule(self):
        pattern = "=-"
        pattern_iterator = itertools.cycle(pattern)
        return self.paragraph("".join(next(pattern_iterator) for _ in range(self.COLUMN_WIDTH)))

    def linebreak(self):
        return "\n"

    def list(self, body, ordered=True):
        def _get_list_marker():
            decimal = count(1)
            return lambda _: f"{next(decimal)}." if ordered else "•"

        return "".join(
            (
                self.linebreak(),
                re.sub(
                    magic_sequence_regex,
                    _get_list_marker(),
                    body,
                ),
            )
        )

    def list_item(self, text):
        return "".join(
            (
                self.linebreak(),
                MAGIC_SEQUENCE,
                " ",
                text.strip(),
            )
        )

    def paragraph(self, text):
        if text.strip():
            return "".join(
                (
                    self.linebreak() * 2,
                    text,
                )
            )
        return ""

    def block_quote(self, text):
        return text

    def link(self, link, title, content):
        return "".join(
            (
                content,
                f" ({title})" if title else "",
                ": ",
                link,
            )
        )

    def autolink(self, link, is_email=False):
        return link


class NotifyEmailPreheaderMarkdownRenderer(NotifyPlainTextEmailMarkdownRenderer):
    def header(self, text, level, raw=None):
        return self.paragraph(text)

    def hrule(self):
        return ""

    def link(self, link, title, content):
        return "".join(
            (
                content,
                f" ({title})" if title else "",
            )
        )


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
notify_letter_qrcode_validator = mistune.Markdown(
    renderer=NotifyLetterMarkdownValidatingRenderer(), hard_wrap=True, use_xhtml=False
)
