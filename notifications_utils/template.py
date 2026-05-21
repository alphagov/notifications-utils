import math
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from functools import lru_cache
from html import unescape
from os import path
from typing import Literal

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from markupsafe import Markup

from notifications_utils import (
    ENGLISH_TO_WELSH_MONTHS,
    LETTER_MAX_PAGE_COUNT,
    MAGIC_SEQUENCE,
    SMS_CHAR_COUNT_LIMIT,
)
from notifications_utils.field import Field, PlainTextField
from notifications_utils.formatters import (
    add_prefix,
    add_trailing_newline,
    autolink_urls,
    escape_html,
    make_quotes_smart,
    nl2br,
    normalise_multiple_newlines,
    normalise_whitespace,
    normalise_whitespace_and_newlines,
    remove_smart_quotes_from_email_addresses,
    remove_whitespace_before_punctuation,
    replace_hyphens_with_en_dashes,
    replace_hyphens_with_non_breaking_hyphens,
    restore_svg_dashes,
    sms_encode,
    strip_leading_whitespace,
    strip_unsupported_characters,
    unlink_govuk_escaped,
)
from notifications_utils.insensitive_dict import InsensitiveDict
from notifications_utils.markdown import (
    notify_email_markdown,
    notify_email_preheader_markdown,
    notify_letter_preview_markdown,
    notify_letter_qrcode_validator,
    notify_plain_text_email_markdown,
)
from notifications_utils.qr_code import QrCodeTooLong
from notifications_utils.recipient_validation.postal_address import PostalAddress, address_lines_1_to_7_keys
from notifications_utils.sanitise_text import SanitiseSMS
from notifications_utils.take import Take
from notifications_utils.timezones import utc_string_to_aware_gmt_datetime

template_env = Environment(
    loader=FileSystemLoader(
        path.join(
            path.dirname(path.abspath(__file__)),
            "jinja_templates",
        )
    ),
    undefined=StrictUndefined,
)


class Template(ABC):
    def __init__(
        self,
        template,
        values=None,
        redact_missing_personalisation=False,
    ):
        if not isinstance(template, dict):
            raise TypeError("Template must be a dict")
        if values is not None and not isinstance(values, dict):
            raise TypeError("Values must be a dict")
        if template.get("template_type") != self.template_type:
            raise TypeError(
                f"Cannot initialise {self.__class__.__name__} with {template.get('template_type')} template_type"
            )
        self.id = template.get("id", None)
        self.name = template.get("name", None)
        self.content = template["content"]
        self.welsh_content = template.get("letter_welsh_content", None)
        self._template = template
        self.values = values
        self.redact_missing_personalisation = redact_missing_personalisation

    def __repr__(self):
        return f'{self.__class__.__name__}("{self.content}", {self.values})'

    @abstractmethod
    def __str__(self):
        pass

    @property
    def content_with_placeholders_filled_in(self):
        return str(
            Field(
                self.content,
                self.values,
                html="passthrough",
                redact_missing_personalisation=self.redact_missing_personalisation,
                markdown_lists=True,
            )
        ).strip()

    @property
    def values(self):
        if hasattr(self, "_values"):
            return self._values
        return {}

    @values.setter
    def values(self, value):
        if not value:
            self._values = {}
        else:
            placeholders = InsensitiveDict.from_keys(self.placeholders)
            self._values = InsensitiveDict(value).as_dict_with_keys(
                self.placeholders
                | {key for key in value.keys() if InsensitiveDict.make_key(key) not in placeholders.keys()}
            )

    @property
    def placeholders(self):
        welsh = set()
        if self.welsh_content:
            welsh = get_placeholders(self.welsh_content)
        english = get_placeholders(self.content)
        all = welsh | english
        return all

    @property
    def missing_data(self):
        return [placeholder for placeholder in self.placeholders if self.values.get(placeholder) is None]

    @property
    def additional_data(self):
        return self.values.keys() - self.placeholders

    def get_raw(self, key, default=None):
        return self._template.get(key, default)

    @property
    def content_count(self):
        return len(self.content_with_placeholders_filled_in)

    def is_message_empty(self):
        if not self.content:
            return True

        if not self.content.startswith("((") or not self.content.endswith("))"):
            return False

        return self.content_count == 0

    def is_message_too_long(self):
        return False


class BaseSMSTemplate(Template):
    template_type = "sms"

    def __init__(
        self,
        template,
        values=None,
        prefix=None,
        show_prefix=True,
        sender=None,
    ):
        self.prefix = prefix
        self.show_prefix = show_prefix
        self.sender = sender
        self._content_count = None
        super().__init__(template, values)

    @property
    def values(self):
        return super().values

    @values.setter
    def values(self, value):
        if self._content_count is not None:
            self._content_count = None
        super(BaseSMSTemplate, type(self)).values.fset(self, value)

    @property
    def content_with_placeholders_filled_in(self):
        return SMSMessageTemplate.__str__(self)

    @property
    def prefix(self):
        return self._prefix if self.show_prefix else None

    @prefix.setter
    def prefix(self, value):
        self._prefix = value

    @property
    def content_count(self):
        if self._content_count is None:
            self._content_count = len(self._get_unsanitised_content())
        return self._content_count

    @property
    def content_count_without_prefix(self):
        if self.prefix:
            return max((self.content_count - len(self.prefix) - 2), 0)
        else:
            return self.content_count

    @property
    def fragment_count(self):
        if self.values:
            # If real data exists, measure the actual rendered text
            content_to_measure = str(self)
        else:
            # Replicate template character count cleanly.
            # Replace placeholders with a standard 7-character string.
            content_to_measure = self.content
            for placeholder in self.placeholders:
                content_to_measure = content_to_measure.replace(f"(({placeholder}))", "7654321")
            
            # Clean up leading/trailing spaces just like the network optimizer does
            content_to_measure = content_to_measure.strip()
            
        return get_sms_fragment_count(content_to_measure)

    def is_message_too_long(self):
        return self.content_count_without_prefix > SMS_CHAR_COUNT_LIMIT

    def is_message_empty(self):
        return self.content_count_without_prefix == 0

    def _get_unsanitised_content(self):
        if self.values:
            values = self.values
        else:
            values = dict.fromkeys(self.placeholders, MAGIC_SEQUENCE)
        return (
            Take(PlainTextField(self.content, values, html="passthrough"))
            .then(add_prefix, self.prefix)
            .then(remove_whitespace_before_punctuation)
            .then(normalise_whitespace_and_newlines)
            .then(normalise_multiple_newlines)
            .then(str.strip)
            .then(str.replace, MAGIC_SEQUENCE, "")
        )


class SMSMessageTemplate(BaseSMSTemplate):
    def __str__(self):
        return sms_encode(self._get_unsanitised_content())


class SMSBodyPreviewTemplate(BaseSMSTemplate):
    def __init__(
        self,
        template,
        values=None,
    ):
        super().__init__(template, values, show_prefix=False)

    def __str__(self):
        return Markup(
            Take(
                Field(
                    self.content,
                    self.values,
                    html="escape",
                    redact_missing_personalisation=True,
                )
            )
            .then(sms_encode)
            .then(remove_whitespace_before_punctuation)
            .then(normalise_whitespace_and_newlines)
            .then(normalise_multiple_newlines)
            .then(str.strip)
        )


class SMSPreviewTemplate(BaseSMSTemplate):
    jinja_template = template_env.get_template("sms_preview_template.jinja2")

    def __init__(
        self,
        template,
        values=None,
        prefix=None,
        show_prefix=True,
        sender=None,
        show_recipient=False,
        show_sender=False,
        downgrade_non_sms_characters=True,
        redact_missing_personalisation=False,
    ):
        self.show_recipient = show_recipient
        self.show_sender = show_sender
        self.downgrade_non_sms_characters = downgrade_non_sms_characters
        super().__init__(template, values, prefix, show_prefix, sender)
        self.redact_missing_personalisation = redact_missing_personalisation

    def __str__(self):
        # Keep the prefix clean for the standard formatter helper
        clean_prefix = (escape_html(self.prefix) or None) if self.show_prefix else None

        # Build the formatted body using the standard pipeline
        formatted_body = str(
            Take(
                Field(
                    self.content,
                    self.values,
                    html="escape",
                    redact_missing_personalisation=self.redact_missing_personalisation,
                )
            )
            .then(add_prefix, clean_prefix)
            .then(sms_encode if self.downgrade_non_sms_characters else str)
            .then(remove_whitespace_before_punctuation)
            .then(normalise_whitespace_and_newlines)
            .then(normalise_multiple_newlines)
        )

        # Check for the combined prefix + colon string generated by add_prefix
        prefix_with_colon = f"{clean_prefix}:" if clean_prefix else None

        if prefix_with_colon and formatted_body.startswith(prefix_with_colon):
            # Slice right AFTER the colon, then strip out any leading spaces from the text body
            body_without_prefix = formatted_body[len(prefix_with_colon):].lstrip()
            final_body = f"{prefix_with_colon}\n{body_without_prefix}"
        else:
            final_body = formatted_body

        # Complete the final HTML preview rendering steps (line breaks and links)
        final_html_body = (
            Take(final_body)
            .then(nl2br)
            .then(
                autolink_urls,
                classes="govuk-link govuk-link--no-visited-state",
            )
        )

        return Markup(
            self.jinja_template.render(
                {
                    "sender": self.sender,
                    "show_sender": self.show_sender,
                    "recipient": Field("((phone number))", self.values, with_brackets=False, html="escape"),
                    "show_recipient": self.show_recipient,
                    "body": final_html_body,
                }
            )
        )
class SubjectMixin:
    def __init__(self, template, values=None, language: Literal["english", "welsh"] = "english", **kwargs):
        welsh_subject = template.get("letter_welsh_subject", "")

        if language == "english":
            self._subject = template["subject"]
        else:
            self._subject = welsh_subject

        self._welsh_subject = welsh_subject

        super().__init__(template, values, **kwargs)

    @property
    def subject(self):
        return Markup(
            Take(
                Field(
                    self._subject,
                    self.values,
                    html="escape",
                    redact_missing_personalisation=self.redact_missing_personalisation,
                )
            )
            .then(do_nice_typography)
            .then(normalise_whitespace)
        )

    @property
    def placeholders(self):
        welsh = set()
        if self._welsh_subject:
            welsh = get_placeholders(self._welsh_subject)
        english = get_placeholders(self._subject)
        all = welsh | english

        return all | super().placeholders


class BaseEmailTemplate(SubjectMixin, Template):
    template_type = "email"

    def __init__(self, template, values=None, unsubscribe_link=None, **kwargs):
        self.unsubscribe_link = unsubscribe_link
        super().__init__(template, values, **kwargs)

    @property
    def content_with_unsubscribe_link(self):
        if self.unsubscribe_link:
            return f"{self.content}\n\n---\n\n[Unsubscribe from these emails]({self.unsubscribe_link})"
        return self.content

    @property
    def html_body(self):
        return (
            Take(
                Field(
                    self.content_with_unsubscribe_link,
                    self.values,
                    html="escape",
                    markdown_lists=True,
                    redact_missing_personalisation=self.redact_missing_personalisation,
                )
            )
            .then(unlink_govuk_escaped)
            .then(strip_unsupported_characters)
            .then(add_trailing_newline)
            .then(notify_email_markdown)
            .then(do_nice_typography)
        )

    @property
    def content_size_in_bytes(self):
        return len(self.content_with_placeholders_filled_in.encode("utf8"))

    def is_message_too_long(self):
        return self.content_size_in_bytes > 2000000


class PlainTextEmailTemplate(BaseEmailTemplate):
    def __str__(self):
        return (
            Take(Field(self.content_with_unsubscribe_link, self.values, html="passthrough", markdown_lists=True))
            .then(unlink_govuk_escaped)
            .then(strip_unsupported_characters)
            .then(add_trailing_newline)
            .then(notify_plain_text_email_markdown)
            .then(do_nice_typography)
            .then(unescape)
            .then(strip_leading_whitespace)
            .then(add_trailing_newline)
        )

    @property
    def subject(self):
        return Markup(
            Take(
                Field(
                    self._subject,
                    self.values,
                    html="passthrough",
                    redact_missing_personalisation=self.redact_missing_personalisation,
                )
            )
            .then(do_nice_typography)
            .then(normalise_whitespace)
        )


class HTMLEmailTemplate(BaseEmailTemplate):
    jinja_template = template_env.get_template("email_template.jinja2")
    PREHEADER_LENGTH_IN_CHARACTERS = 256

    def __init__(
        self,
        template,
        values=None,
        govuk_banner=True,
        complete_html=True,
        brand_logo=None,
        brand_text=None,
        brand_colour=None,
        brand_banner=False,
        brand_alt_text=None,
        rebrand=False,
        **kwargs,
    ):
        super().__init__(template, values, **kwargs)
        self.govuk_banner = govuk_banner
        self.complete_html = complete_html
        self.brand_logo = brand_logo
        self.brand_text = brand_text
        self.brand_colour = brand_colour
        self.brand_banner = brand_banner
        self.brand_alt_text = brand_alt_text
        self.rebrand = rebrand

    @property
    def preheader(self):
        return " ".join(
            Take(
                Field(
                    self.content,
                    self.values,
                    html="escape",
                    markdown_lists=True,
                )
            )
            .then(unlink_govuk_escaped)
            .then(strip_unsupported_characters)
            .then(add_trailing_newline)
            .then(notify_email_preheader_markdown)
            .then(do_nice_typography)
            .split()
        )[: self.PREHEADER_LENGTH_IN_CHARACTERS].strip()

    def __str__(self):
        return self.jinja_template.render(
            {
                "subject": self.subject,
                "body": self.html_body,
                "preheader": self.preheader,
                "govuk_banner": self.govuk_banner,
                "complete_html": self.complete_html,
                "brand_logo": self.brand_logo,
                "brand_text": self.brand_text,
                "brand_colour": self.brand_colour,
                "brand_banner": self.brand_banner,
                "brand_alt_text": self.brand_alt_text,
                "rebrand": self.rebrand,
            }
        )


class BaseLetterTemplate(SubjectMixin, Template):
    template_type = "letter"
    max_page_count = LETTER_MAX_PAGE_COUNT
    max_sheet_count = LETTER_MAX_PAGE_COUNT // 2

    address_block = "\n".join(f"(({line.replace('_', ' ')}))" for line in address_lines_1_to_7_keys)

    def __init__(
        self,
        template,
        values=None,
        contact_block=None,
        admin_base_url="http://localhost:6012",
        logo_file_name=None,
        redact_missing_personalisation=False,
        date: datetime | None = None,
        language="english",
        includes_first_page: bool = True,
    ):
        self.contact_block = (contact_block or "").strip()
        super().__init__(
            template, values, redact_missing_personalisation=redact_missing_personalisation, language=language
        )
        self.admin_base_url = admin_base_url
        self.logo_file_name = logo_file_name
        self.date = date
        self.language = language
        if language == "english":
            self.content = template["content"]
        else:
            self.content = template.get("letter_welsh_content", "")
        self.includes_first_page = includes_first_page

    @property
    def subject(self):
        return (
            Take(
                Field(
                    self._subject,
                    self.values,
                    redact_missing_personalisation=self.redact_missing_personalisation,
                    html="escape",
                )
            )
            .then(do_nice_typography)
            .then(normalise_whitespace)
        )

    @property
    def placeholders(self):
        return get_placeholders(self.contact_block) | super().placeholders

    @property
    def too_many_pages(self):
        return self.page_count > self.max_page_count

    @property
    def postal_address(self):
        return PostalAddress.from_personalisation(InsensitiveDict(self.values))

    def has_qr_code_with_too_much_data(self) -> QrCodeTooLong | None:
        content = self._personalised_content if self.values else self.content
        try:
            Take(content).then(notify_letter_qrcode_validator)
        except QrCodeTooLong as e:
            return e
        return None

    @property
    def _address_block(self):
        if self.postal_address.has_enough_lines and not self.postal_address.has_too_many_lines:
            return self.postal_address.normalised_lines

        if "address line 7" not in self.values and "postcode" in self.values:
            self.values["address line 7"] = self.values["postcode"]

        return Field(
            self.address_block,
            self.values,
            html="escape",
            with_brackets=False,
        ).splitlines()

    @property
    def _contact_block(self):
        return (
            Take(
                Field(
                    "\n".join(line.strip() for line in self.contact_block.split("\n")),
                    self.values,
                    redact_missing_personalisation=self.redact_missing_personalisation,
                    html="escape",
                )
            )
            .then(remove_whitespace_before_punctuation)
            .then(nl2br)
        )

    @property
    def date(self) -> str:
        month = self._date.strftime("%B")
        if self.language == "welsh":
            month = ENGLISH_TO_WELSH_MONTHS[month]
        return self._date.strftime(f"%-d {month} %Y")

    @date.setter
    def date(self, value: datetime | None):
        self._date = utc_string_to_aware_gmt_datetime(value or datetime.now(UTC)).date()

    @property
    def _personalised_content(self) -> Field:
        return Field(
            self.content,
            self.values,
            html="escape",
            markdown_lists=True,
            redact_missing_personalisation=self.redact_missing_personalisation,
        )

    @property
    def _message(self):
        return (
            Take(self._personalised_content)
            .then(add_trailing_newline)
            .then(notify_letter_preview_markdown)
            .then(do_nice_typography)
            .then(replace_hyphens_with_non_breaking_hyphens)
            .then(restore_svg_dashes)
        )


class LetterPreviewTemplate(BaseLetterTemplate):
    jinja_template = template_env.get_template("letter_pdf/preview.jinja2")

    @property
    def render_params(self):
        return {
            "admin_base_url": self.admin_base_url,
            "logo_file_name": self.logo_file_name,
            "logo_class": self.logo_file_name.lower()[-3:] if self.logo_file_name else None,
            "subject": self.subject,
            "message": self._message,
            "address": self._address_block,
            "contact_block": self._contact_block,
            "date": self.date,
            "language": self.language,
            "includes_first_page": self.includes_first_page,
        }

    def __str__(self):
        return Markup(self.jinja_template.render(self.render_params))


class LetterPrintTemplate(LetterPreviewTemplate):
    jinja_template = template_env.get_template("letter_pdf/print.jinja2")

    def __init__(
        self,
        template,
        values=None,
        contact_block=None,
        admin_base_url="http://localhost:6012",
        logo_file_name=None,
        redact_missing_personalisation=False,
        date=None,
        language="english",
        includes_first_page: bool = True,
    ):
        super().__init__(
            template,
            values=values,
            contact_block=contact_block,
            admin_base_url=admin_base_url,
            logo_file_name=logo_file_name,
            redact_missing_personalisation=redact_missing_personalisation,
            date=date,
            language=language,
        )
        self.includes_first_page = includes_first_page

    @property
    def render_params(self):
        return super().render_params | {"includes_first_page": self.includes_first_page}


def get_sms_fragment_count(content):
    """
    Calculates SMS message fragments based on how characters are packed over the network.
    - GSM 7-bit allows 160 chars (153 if concatenated). Extended chars count as 2.
    - UCS-2 (non-GSM multi-language/emojis) drops boundaries to 70 units (67 if concatenated).
    """
    if non_gsm_characters(content):
        # Multi-language scripts/emojis use 16-bit units on cellular networks.
        # Encoding to UTF-16-BE and dividing bytes by 2 safely counts surrogate pairs as 2 units.
        encoded_units = len(content.encode('utf-16-be')) // 2
        return 1 if encoded_units <= 70 else math.ceil(float(encoded_units) / 67)
    else:
        # Standard GSM 7-bit math where basic characters are 1 unit, and extended characters are 2.
        total_gsm_units = len(content) + count_extended_gsm_chars(content)
        return 1 if total_gsm_units <= 160 else math.ceil(float(total_gsm_units) / 153)


def non_gsm_characters(content):
    """
    Returns True if the content contains any characters outside the standard 7-bit GSM alphabet.
    This safely handles the fragment limit shift for global scripts like Hebrew or Arabic.
    """
    gsm_7bit_charset = set(
        "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞ\x1bÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?"
        "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà"
        "^{}\\[~]|€"
    )
    return any(c not in gsm_7bit_charset for c in content)


def count_extended_gsm_chars(content):
    """
    Returns how many extended characters exist in the content.
    Extended characters only double the size when utilizing standard basic GSM 7-bit packing pipelines.
    """
    if non_gsm_characters(content):
        return 0
    extended_gsm_characters = set("^{}\\[~]|€")
    return sum(map(content.count, extended_gsm_characters))


def do_nice_typography(value):
    return (
        Take(value)
        .then(remove_whitespace_before_punctuation)
        .then(make_quotes_smart)
        .then(remove_smart_quotes_from_email_addresses)
        .then(replace_hyphens_with_en_dashes)
    )


@lru_cache(maxsize=1024)
def get_placeholders(content):
    return Field(content).placeholders