import re
import string
from collections.abc import Sequence

# Type hint error ignored (until mypy brings in https://github.com/python/typeshed/pull/15925)
from html import _replace_charref, escape  # type: ignore[attr-defined]
from sys import maxsize
from typing import Any
from urllib.parse import quote

import smartypants
from markupsafe import Markup

from notifications_utils.sanitise_text import SanitiseSMS

from . import email_with_smart_quotes_regex

OBSCURE_ZERO_WIDTH_WHITESPACE = (
    "\u180e"  # Mongolian vowel separator
    "\u200b"  # zero width space
    "\u200c"  # zero width non-joiner
    "\u200d"  # zero width joiner
    "\u2060"  # word joiner
    "\ufeff"  # zero width non-breaking space
    "\u2028"  # line separator
    "\u2029"  # paragraph separator
)

OBSCURE_FULL_WIDTH_WHITESPACE = "\u00a0\u202f"  # non breaking space  # narrow no break space

ALL_WHITESPACE = string.whitespace + OBSCURE_ZERO_WIDTH_WHITESPACE + OBSCURE_FULL_WIDTH_WHITESPACE

RECOGNISED_URL_PROTOCOLS = tuple(f"{protocol}:" for protocol in {"ftp", "file", "http", "https", "mailto", "tel"})

govuk_not_a_link = re.compile(r"(^|\s)(#|\*|\^)?(GOV)\.(UK)(?!\/|\?|#)", re.IGNORECASE)

smartypants.tags_to_skip = smartypants.tags_to_skip + ["a"]

whitespace_before_punctuation = re.compile(r"(?<![ \t])[ \t]+([,\.])")

hyphens_surrounded_by_spaces = re.compile(r"(?<!\s)\s+[-–—]{1,3}\s+")  # check three different unicode hyphens

multiple_newlines = re.compile(r"((\n)\2{2,})")

HTML_ENTITY_MAPPING = (
    ("&nbsp;", "👾🐦🥴"),
    ("&amp;", "➕🐦🥴"),
)

url = re.compile(
    r"(?i)"  # case insensitive
    r"\b(?<![\@\.])"  # match must not start with @ or . (like @test.example.com)
    r"(https?:\/\/)?"  # optional http:// or https://
    r"([\w\-]+\.{1})+"  # one or more (sub)domains
    r"([a-z]{2,63})"  # top-level domain
    r"(?!\@)\b"  # match must not end with @ (like firstname.lastname@)
    r"([/\?#][^<\s]*)?"  # start of path, query or fragment
)

more_than_two_newlines_in_a_row = re.compile(r"\n{3,}")


def unlink_govuk_escaped(message: str) -> str:
    return re.sub(govuk_not_a_link, r"\1\2\3" + ".\u200b" + r"\4", message)  # Unicode zero-width space


def nl2br(value: str) -> str:
    return re.sub(r"\n|\r", "<br>", value.strip())


def add_prefix(body: str, prefix: str | None = None) -> str:
    if prefix:
        return f"{prefix.strip()}: {body}"
    return body


def make_link_from_url(linked_part, *, classes=""):
    """
    Takes something which looks like a URL, works out which trailing characters shouldn’t
    be considered part of the link and returns an HTML <a> tag

    input: `http://example.com/foo_(bar)).`
    output: `<a href="http://example.com/foo_(bar)">http://example.com/foo_(bar)</a>).`
    """
    CORRESPONDING_OPENING_CHARACTER_MAP = {
        ")": "(",
        "]": "[",
        ".": None,
        ",": None,
        ":": None,
    }

    trailing_characters = ""

    while (last_character := linked_part[-1]) in CORRESPONDING_OPENING_CHARACTER_MAP.keys():
        corresponding_opening_character = CORRESPONDING_OPENING_CHARACTER_MAP[last_character]

        if corresponding_opening_character:
            count_opening_characters = linked_part.count(corresponding_opening_character)
            count_closing_characters = linked_part.count(last_character)
            if count_opening_characters >= count_closing_characters:
                break

        trailing_characters = linked_part[-1] + trailing_characters
        linked_part = linked_part[:-1]

    return f"{create_sanitised_html_for_url(linked_part, classes=classes)}{trailing_characters}"


def autolink_urls(value, *, classes=""):
    return Markup(
        url.sub(
            lambda match: make_link_from_url(
                match.group(0),
                classes=classes,
            ),
            value,
        )
    )


def create_sanitised_html_for_url(
    link: str, *, classes: str = "", style: str = "", title: str = "", link_text: str = ""
) -> str:
    """
    takes a link and returns an <a> tag to that link. We escape the link that goes into the `href` attribute to
    prevent XSS attacks (eg through double-quotes). Notably we don't escape _all_ escape-able values,
    as some URLs may be sent to us with already urlencoded values (eg %20) - we don't want to end up double-escaping
    these as they should reach the target server un-mangled.

    input: `http://foo.com/"bar"?x=1&redirect=%2Fsuccess%3Fone#2`
    output: `<a style=... href="http://foo.com/%22bar%22?x=1&redirect=%2Fsuccess%3Fone#2">
               http://foo.com/"bar"?x=1&redirect=%2Fsuccess%3Fone#2
             </a>`
    """
    if not link_text:
        link_text = link

    if not link.lower().startswith(RECOGNISED_URL_PROTOCOLS):
        link = f"http://{link}"

    class_attribute = f'class="{classes}" ' if classes else ""
    style_attribute = f'style="{style}" ' if style else ""

    safe_link = quote(link, safe=":/?#=&;%")

    if title:
        return f'<a {class_attribute}{style_attribute}href="{safe_link}" title="{title}">{link_text}</a>'

    return f'<a {class_attribute}{style_attribute}href="{safe_link}">{link_text}</a>'


def prepend_subject(body: str, subject: str) -> str:
    return f"# {subject}\n\n{body}"


def sms_encode(content: str) -> str:
    return SanitiseSMS.encode(content)


"""
Re-implements html._charref but makes trailing semicolons non-optional
"""
_charref = re.compile(r"&(#[0-9]+;|#[xX][0-9a-fA-F]+;|[^\t\n\f <&#;]{1,32};)")


def unescape_strict(s: str) -> str:
    """
    Re-implements html.unescape to use our own definition of `_charref`
    """
    if "&" not in s:
        return s
    return _charref.sub(_replace_charref, s)


def escape_html(value: str | None) -> str | None:
    if not value:
        return value
    value = str(value)

    for entity, temporary_replacement in HTML_ENTITY_MAPPING:
        value = value.replace(entity, temporary_replacement)

    value = escape(unescape_strict(value), quote=False)

    for entity, temporary_replacement in HTML_ENTITY_MAPPING:
        value = value.replace(temporary_replacement, entity)

    return value


def url_encode_full_stops(value: str) -> str:
    return value.replace(".", "%2E")


def unescaped_formatted_list(
    items: Sequence[Any],
    *,
    conjunction: str = "and",
    before_each: str = "‘",
    after_each: str = "’",
    separator: str = ", ",
    prefix: str = "",
    prefix_plural: str = "",
    max_items_shown: int = maxsize,
    word_for_items_not_shown: str = "",
) -> str:
    if max_items_shown < maxsize and not word_for_items_not_shown:
        raise TypeError('`word_for_items_not_shown` must be provided, for example "more" or "others"')

    if not items:
        return ""

    if prefix:
        prefix += " "
    if prefix_plural:
        prefix_plural += " "

    if len(items) > max_items_shown:
        cutoff = max(max_items_shown - 1, 1)
        formatted_items = [f"{before_each}{item}{after_each}" for item in items[:cutoff]] + [word_for_items_not_shown]
    else:
        formatted_items = [f"{before_each}{item}{after_each}" for item in items]

    if len(items) == 1:
        return f"{prefix}{formatted_items[0]}"

    first_items = separator.join(formatted_items[:-1])
    last_item = formatted_items[-1]
    return f"{prefix_plural}{first_items} {conjunction} {last_item}"


def formatted_list(items: Sequence[Any], **kwargs) -> Markup:
    return Markup(unescaped_formatted_list([escape_html(x) for x in items], **kwargs))


def remove_whitespace_before_punctuation(value: str) -> str:
    return re.sub(whitespace_before_punctuation, lambda match: match.group(1), value)


def make_quotes_smart(value: str) -> str:
    return smartypants.smartypants(value, smartypants.Attr.q | smartypants.Attr.u)


def replace_hyphens_with_en_dashes(value: str) -> str:
    return re.sub(
        hyphens_surrounded_by_spaces,
        (" \u2013 "),  # space  # en dash  # space
        value,
    )


SVG_DASH_REPLACEMENT = "🛳️🐦🥴"


def replace_svg_dashes(value: str) -> str:
    return value.replace("-", SVG_DASH_REPLACEMENT)


def replace_hyphens_with_non_breaking_hyphens(value: str) -> str:
    return value.replace(
        "-",
        "\u2011",  # non-breaking hyphen
    )


def restore_svg_dashes(value: str) -> str:
    return value.replace(SVG_DASH_REPLACEMENT, "-")


def normalise_whitespace_and_newlines(value: str) -> str:
    return "\n".join(get_lines_with_normalised_whitespace(value))


def get_lines_with_normalised_whitespace(value: str) -> list:
    return [normalise_whitespace(line) for line in value.splitlines()]


def normalise_whitespace(value: str) -> str:
    # leading and trailing whitespace removed
    # inner whitespace with width becomes a single space
    # inner whitespace with zero width is removed
    # multiple space characters next to each other become just a single space character
    for character in OBSCURE_FULL_WIDTH_WHITESPACE:
        value = value.replace(character, " ")

    for character in OBSCURE_ZERO_WIDTH_WHITESPACE:
        value = value.replace(character, "")

    return " ".join(value.split())


def normalise_multiple_newlines(value: str) -> str:
    return more_than_two_newlines_in_a_row.sub("\n\n", value)


def strip_leading_whitespace(value: str) -> str:
    return value.lstrip()


def add_trailing_newline(value: str) -> str:
    return f"{value}\n"


def remove_smart_quotes_from_email_addresses(value: str) -> str:
    def remove_smart_quotes(match: re.Match) -> str:
        value = match.group(0)
        for character in "‘’":
            value = value.replace(character, "'")
        return value

    return email_with_smart_quotes_regex.sub(
        remove_smart_quotes,
        value,
    )


def strip_all_whitespace(value: str, extra_trailing_characters: str = "") -> str:
    # Removes:
    # - all whitespace characters from beginning and end of the string
    # - and also any `extra_trailing_characters` from just the end of the string
    if value is not None and hasattr(value, "lstrip") and hasattr(value, "rstrip"):
        return value.lstrip(ALL_WHITESPACE).rstrip(ALL_WHITESPACE + extra_trailing_characters)
    return value


def strip_and_remove_obscure_whitespace(value: str) -> str:
    if value == "":
        # Return early to avoid making multiple, slow calls to
        # str.replace on an empty string
        return ""

    for character in OBSCURE_ZERO_WIDTH_WHITESPACE + OBSCURE_FULL_WIDTH_WHITESPACE:
        value = value.replace(character, "")

    return value.strip(string.whitespace)


def remove_whitespace(value: str) -> str:
    # Removes ALL whitespace, not just the obscure characters we normaly remove
    for character in ALL_WHITESPACE:
        value = value.replace(character, "")

    return value


def strip_unsupported_characters(value: str) -> str:
    return value.replace("\u2028", "").replace("\u3164", "")


def format_file_size(number_of_bytes: int) -> str:
    if number_of_bytes < 1024 / 20:
        # File less than 0.05KB (one twentieth of a KB) don't round to 0.1KB at 1 d.p.
        # We will force them up to 0.1KB ourselves as we don't want to show users 0.0KB or bytes
        return "0.1KB"
    elif number_of_bytes < (1024**2) / 20:
        # File less than 0.05MB to be represented in KB
        # Anything bigger will round at 1dp to at least 0.1MB
        kb_to_1dp = round(number_of_bytes / 1024, 1)
        return str(kb_to_1dp).rstrip(".0") + "KB"
    else:
        mb_to_1dp = round(number_of_bytes / (1024**2), 1)
        return str(mb_to_1dp).rstrip(".0") + "MB"
