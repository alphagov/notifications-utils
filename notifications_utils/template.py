import math
from os import path
from datetime import datetime

from jinja2 import Environment, FileSystemLoader
from flask import Markup
from html import unescape

from notifications_utils import LETTER_MAX_PAGE_COUNT, SMS_CHAR_COUNT_LIMIT
from notifications_utils.columns import Columns
from notifications_utils.field import Field
from notifications_utils.formatters import (
    unlink_govuk_escaped,
    nl2br,
    nl2li,
    add_prefix,
    autolink_sms,
    notify_email_markdown,
    notify_email_preheader_markdown,
    notify_plain_text_email_markdown,
    notify_letter_preview_markdown,
    remove_empty_lines,
    sms_encode,
    escape_html,
    strip_dvla_markup,
    strip_pipes,
    remove_whitespace_before_punctuation,
    make_quotes_smart,
    replace_hyphens_with_en_dashes,
    replace_hyphens_with_non_breaking_hyphens,
    tweak_dvla_list_markup,
    strip_leading_whitespace,
    add_trailing_newline,
    normalise_newlines,
    normalise_whitespace,
    remove_smart_quotes_from_email_addresses,
    strip_unsupported_characters,
)
from notifications_utils.take import Take
from notifications_utils.template_change import TemplateChange
from notifications_utils.sanitise_text import SanitiseSMS


template_env = Environment(loader=FileSystemLoader(
    path.join(
        path.dirname(path.abspath(__file__)),
        'jinja_templates',
    )
))


class Template():

    encoding = "utf-8"

    def __init__(
        self,
        template,
        values=None,
        redact_missing_personalisation=False,
    ):
        if not isinstance(template, dict):
            raise TypeError('Template must be a dict')
        if values is not None and not isinstance(values, dict):
            raise TypeError('Values must be a dict')
        self.id = template.get("id", None)
        self.name = template.get("name", None)
        self.content = template["content"]
        self.values = values
        self.template_type = template.get('template_type', None)
        self._template = template
        self.redact_missing_personalisation = redact_missing_personalisation

    def __repr__(self):
        return "{}(\"{}\", {})".format(self.__class__.__name__, self.content, self.values)

    def __str__(self):
        return Markup(Field(
            self.content,
            self.values,
            html='escape',
            redact_missing_personalisation=self.redact_missing_personalisation
        ))

    @property
    def values(self):
        if hasattr(self, '_values'):
            return self._values
        return {}

    @values.setter
    def values(self, value):
        if not value:
            self._values = {}
        else:
            placeholders = Columns.from_keys(self.placeholders)
            self._values = Columns(value).as_dict_with_keys(
                self.placeholders | set(
                    key for key in value.keys()
                    if Columns.make_key(key) not in placeholders.keys()
                )
            )

    @property
    def placeholders(self):
        return Field(self.content).placeholders

    @property
    def missing_data(self):
        return list(
            placeholder for placeholder in self.placeholders
            if self.values.get(placeholder) is None
        )

    @property
    def additional_data(self):
        return self.values.keys() - self.placeholders

    def get_raw(self, key, default=None):
        return self._template.get(key, default)

    def compare_to(self, new):
        return TemplateChange(self, new)

    def is_message_too_long(self):
        return False


class SMSMessageTemplate(Template):

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
        super().__init__(template, values)

    def __str__(self):
        return Take(Field(
            self.content, self.values, html='passthrough'
        )).then(
            add_prefix, self.prefix
        ).then(
            sms_encode
        ).then(
            remove_whitespace_before_punctuation
        ).then(
            normalise_newlines
        ).then(
            str.strip
        )

    @property
    def prefix(self):
        return self._prefix if self.show_prefix else None

    @prefix.setter
    def prefix(self, value):
        self._prefix = value

    @property
    def content_count(self):
        """
        Return the number of characters in the message. Note that we don't distinguish between GSM and non-GSM
        characters at this point, as `get_sms_fragment_count` handles that separately.

        Also note that if values aren't provided, will calculate the raw length of the unsubstituted placeholders,
        as in the message `foo ((placeholder))` has a length of 19.
        """
        return len(
            # we always want to call SMSMessageTemplate.__str__ regardless of subclass, to avoid any html formatting
            SMSMessageTemplate.__str__(self)
            if self._values
            else sms_encode(add_prefix(self.content.strip(), self.prefix))
        )

    @property
    def fragment_count(self):
        content_with_placeholders = str(self)
        return get_sms_fragment_count(self.content_count, is_unicode(content_with_placeholders))

    def is_message_too_long(self):
        return self.content_count > SMS_CHAR_COUNT_LIMIT


class SMSPreviewTemplate(SMSMessageTemplate):

    jinja_template = template_env.get_template('sms_preview_template.jinja2')

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

        return Markup(self.jinja_template.render({
            'sender': self.sender,
            'show_sender': self.show_sender,
            'recipient': Field('((phone number))', self.values, with_brackets=False, html='escape'),
            'show_recipient': self.show_recipient,
            'body': Take(Field(
                self.content,
                self.values,
                html='escape',
                redact_missing_personalisation=self.redact_missing_personalisation,
            )).then(
                add_prefix, (escape_html(self.prefix) or None) if self.show_prefix else None
            ).then(
                sms_encode if self.downgrade_non_sms_characters else str
            ).then(
                remove_whitespace_before_punctuation
            ).then(
                nl2br
            ).then(
                autolink_sms
            )
        }))


class WithSubjectTemplate(Template):

    def __init__(
        self,
        template,
        values=None,
        redact_missing_personalisation=False,
    ):
        self._subject = template['subject']
        super().__init__(template, values, redact_missing_personalisation=redact_missing_personalisation)

    def __str__(self):
        return str(Field(
            self.content,
            self.values,
            html='passthrough',
            redact_missing_personalisation=self.redact_missing_personalisation,
            markdown_lists=True,
        ))

    @property
    def subject(self):
        return Markup(Take(Field(
            self._subject,
            self.values,
            html='escape',
            redact_missing_personalisation=self.redact_missing_personalisation,
        )).then(
            do_nice_typography
        ).then(
            normalise_whitespace
        ))

    @property
    def placeholders(self):
        return Field(self._subject).placeholders | Field(self.content).placeholders

    @property
    def content_count(self):
        return len(WithSubjectTemplate.__str__(self).strip() if self._values else self.content.strip())


class PlainTextEmailTemplate(WithSubjectTemplate):

    def __str__(self):
        return Take(Field(
            self.content, self.values, html='passthrough', markdown_lists=True
        )).then(
            unlink_govuk_escaped
        ).then(
            strip_unsupported_characters
        ).then(
            add_trailing_newline
        ).then(
            notify_plain_text_email_markdown
        ).then(
            do_nice_typography
        ).then(
            unescape
        ).then(
            strip_leading_whitespace
        ).then(
            add_trailing_newline
        )

    @property
    def subject(self):
        return Markup(Take(Field(
            self._subject,
            self.values,
            html='passthrough',
            redact_missing_personalisation=self.redact_missing_personalisation
        )).then(
            do_nice_typography
        ).then(
            normalise_whitespace
        ))


class HTMLEmailTemplate(WithSubjectTemplate):

    jinja_template = template_env.get_template('email_template.jinja2')

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
        brand_name=None
    ):
        super().__init__(template, values)
        self.govuk_banner = govuk_banner
        self.complete_html = complete_html
        self.brand_logo = brand_logo
        self.brand_text = brand_text
        self.brand_colour = brand_colour
        self.brand_banner = brand_banner
        self.brand_name = brand_name

    @property
    def preheader(self):
        return " ".join(Take(Field(
            self.content,
            self.values,
            html='escape',
            markdown_lists=True,
        )).then(
            unlink_govuk_escaped
        ).then(
            strip_unsupported_characters
        ).then(
            add_trailing_newline
        ).then(
            notify_email_preheader_markdown
        ).then(
            do_nice_typography
        ).split())[:self.PREHEADER_LENGTH_IN_CHARACTERS].strip()

    def __str__(self):

        return self.jinja_template.render({
            'body': get_html_email_body(
                self.content, self.values
            ),
            'preheader': self.preheader,
            'govuk_banner': self.govuk_banner,
            'complete_html': self.complete_html,
            'brand_logo': self.brand_logo,
            'brand_text': self.brand_text,
            'brand_colour': self.brand_colour,
            'brand_banner': self.brand_banner,
            'brand_name': self.brand_name
        })


class EmailPreviewTemplate(WithSubjectTemplate):

    jinja_template = template_env.get_template('email_preview_template.jinja2')

    def __init__(
        self,
        template,
        values=None,
        from_name=None,
        from_address=None,
        reply_to=None,
        show_recipient=True,
        redact_missing_personalisation=False,
    ):
        super().__init__(template, values, redact_missing_personalisation=redact_missing_personalisation)
        self.from_name = from_name
        self.from_address = from_address
        self.reply_to = reply_to
        self.show_recipient = show_recipient

    def __str__(self):
        return Markup(self.jinja_template.render({
            'body': get_html_email_body(
                self.content, self.values, redact_missing_personalisation=self.redact_missing_personalisation
            ),
            'subject': self.subject,
            'from_name': escape_html(self.from_name),
            'from_address': self.from_address,
            'reply_to': self.reply_to,
            'recipient': Field("((email address))", self.values, with_brackets=False),
            'show_recipient': self.show_recipient
        }))

    @property
    def subject(self):
        return Take(Field(
            self._subject,
            self.values,
            html='escape',
            redact_missing_personalisation=self.redact_missing_personalisation
        )).then(
            do_nice_typography
        ).then(
            normalise_whitespace
        )


class LetterPreviewTemplate(WithSubjectTemplate):

    jinja_template = template_env.get_template('letter_pdf/preview.jinja2')

    address_block = '\n'.join([
        '((address line 1))',
        '((address line 2))',
        '((address line 3))',
        '((address line 4))',
        '((address line 5))',
        '((address line 6))',
        '((postcode))',
    ])

    def __init__(
        self,
        template,
        values=None,
        contact_block=None,
        admin_base_url='http://localhost:6012',
        logo_file_name=None,
        redact_missing_personalisation=False,
        date=None,
    ):
        self.contact_block = (contact_block or '').strip()
        super().__init__(template, values, redact_missing_personalisation=redact_missing_personalisation)
        self.admin_base_url = admin_base_url
        self.logo_file_name = logo_file_name
        self.date = date or datetime.utcnow()

    def __str__(self):
        return Markup(self.jinja_template.render({
            'admin_base_url': self.admin_base_url,
            'logo_file_name': self.logo_file_name,
            # logo_class should only ever be None, svg or png
            'logo_class': self.logo_file_name.lower()[-3:] if self.logo_file_name else None,
            'subject': self.subject,
            'message': self._message,
            'address': self._address_block,
            'contact_block': self._contact_block,
            'date': self._date,
        }))

    @property
    def subject(self):
        return Take(Field(
            self._subject,
            self.values,
            redact_missing_personalisation=self.redact_missing_personalisation,
            html='escape',
        )).then(
            do_nice_typography
        ).then(
            strip_pipes
        ).then(
            strip_dvla_markup
        ).then(
            normalise_whitespace
        )

    @property
    def placeholders(self):
        return super().placeholders | Field(self.contact_block).placeholders

    @property
    def values_with_default_optional_address_lines(self):
        keys = Columns.from_keys(
            set(self.values.keys()) | {
                'address line 3',
                'address line 4',
                'address line 5',
                'address line 6',
            }
        ).keys()

        return {
            key: Columns(self.values).get(key) or ''
            for key in keys
        }

    @property
    def _address_block(self):
        return Take(Field(
            self.address_block,
            (
                self.values_with_default_optional_address_lines
                if all(Columns(self.values).get(key) for key in {
                    'address line 1',
                    'address line 2',
                    'postcode',
                }) else self.values
            ),
            html='escape',
            with_brackets=False
        )).then(
            strip_pipes
        ).then(
            remove_empty_lines
        ).then(
            remove_whitespace_before_punctuation
        ).then(
            nl2li
        )

    @property
    def _contact_block(self):
        return Take(Field(
            '\n'.join(
                line.strip()
                for line in self.contact_block.split('\n')
            ),
            self.values,
            redact_missing_personalisation=self.redact_missing_personalisation,
            html='escape',
        )).then(
            remove_whitespace_before_punctuation
        ).then(
            nl2br
        ).then(
            strip_pipes
        )

    @property
    def _date(self):
        return self.date.strftime('%-d %B %Y')

    @property
    def _message(self):
        return Take(Field(
            strip_dvla_markup(self.content),
            self.values,
            html='escape',
            markdown_lists=True,
            redact_missing_personalisation=self.redact_missing_personalisation,
        )).then(
            strip_pipes
        ).then(
            add_trailing_newline
        ).then(
            notify_letter_preview_markdown
        ).then(
            do_nice_typography
        ).then(
            replace_hyphens_with_non_breaking_hyphens
        ).then(
            tweak_dvla_list_markup
        )


class LetterPrintTemplate(LetterPreviewTemplate):

    jinja_template = template_env.get_template('letter_pdf/print.jinja2')


class LetterImageTemplate(LetterPreviewTemplate):

    jinja_template = template_env.get_template('letter_image_template.jinja2')
    first_page_number = 1

    def __init__(
        self,
        template,
        values=None,
        image_url=None,
        page_count=None,
        contact_block=None,
        postage=None,
    ):
        super().__init__(template, values, contact_block=contact_block)
        if not image_url:
            raise TypeError('image_url is required')
        if not page_count:
            raise TypeError('page_count is required')
        if postage not in {None, 'first', 'second'}:
            raise TypeError('postage must be `None`, first or second')
        self.image_url = image_url
        self.page_count = int(page_count)
        self.postage = postage

    @property
    def last_page_number(self):
        return min(self.page_count, LETTER_MAX_PAGE_COUNT) + self.first_page_number

    @property
    def page_numbers(self):
        return list(range(self.first_page_number, self.last_page_number))

    def __str__(self):
        return Markup(self.jinja_template.render({
            'image_url': self.image_url,
            'page_numbers': self.page_numbers,
            'address': self._address_block,
            'contact_block': self._contact_block,
            'date': self._date,
            'subject': self.subject,
            'message': self._message,
            'postage': self.postage,
        }))


class NeededByTemplateError(Exception):
    def __init__(self, keys):
        super(NeededByTemplateError, self).__init__(", ".join(keys))


class NoPlaceholderForDataError(Exception):
    def __init__(self, keys):
        super(NoPlaceholderForDataError, self).__init__(", ".join(keys))


def get_sms_fragment_count(character_count, is_unicode):
    if is_unicode:
        return 1 if character_count <= 70 else math.ceil(float(character_count) / 67)
    else:
        return 1 if character_count <= 160 else math.ceil(float(character_count) / 153)


def is_unicode(content):
    return set(content) & set(SanitiseSMS.WELSH_NON_GSM_CHARACTERS)


def get_html_email_body(template_content, template_values, redact_missing_personalisation=False):

    return Take(Field(
        template_content,
        template_values,
        html='escape',
        markdown_lists=True,
        redact_missing_personalisation=redact_missing_personalisation,
    )).then(
        unlink_govuk_escaped
    ).then(
        strip_unsupported_characters
    ).then(
        add_trailing_newline
    ).then(
        notify_email_markdown
    ).then(
        do_nice_typography
    )


def do_nice_typography(value):
    return Take(
        value
    ).then(
        remove_whitespace_before_punctuation
    ).then(
        make_quotes_smart
    ).then(
        remove_smart_quotes_from_email_addresses
    ).then(
        replace_hyphens_with_en_dashes
    )
