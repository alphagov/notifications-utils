import re
import math
import bleach

from orderedset import OrderedSet
from flask import Markup

from notifications_utils.columns import Columns
from notifications_utils.renderers import HTMLEmail, SMSPreview, EmailPreview, LetterPreview


class Template():

    placeholder_pattern = re.compile(
        '\(\('            # opening ((
        '([^\(\)\?]+)'    # 1. name of placeholder, eg ‘registration number’
        '(\?\?)?'         # 2. optional ??
        '([^\)\(]*)'      # 3. optional text to display if the placeholder’s value is True
        '\)\)'            # closing ))
    )
    placeholder_tag = "<span class='placeholder'>(({}{}))</span>"
    optional_placeholder_tag = "<span class='placeholder-conditional'>(({}??</span>{}))"

    def __init__(
        self,
        template,
        values=None,
        drop_values=(),
        prefix=None,
        sms_sender=None,
        encoding="utf-8",
        content_character_limit=None,
        renderer=None
    ):
        if not isinstance(template, dict):
            raise TypeError('Template must be a dict')
        if values is not None and not isinstance(values, dict):
            raise TypeError('Values must be a dict')
        if prefix is not None and not isinstance(prefix, str):
            raise TypeError('Prefix must be a string')
        self.id = template.get("id", None)
        self.name = template.get("name", None)
        self.content = template["content"]
        self.subject = template.get('subject', None)
        self.values = values
        self.template_type = template.get('template_type', None)
        for value in drop_values:
            self._values.pop(value, None)
        self.encoding = encoding
        self.content_character_limit = content_character_limit
        self._template = template
        self._prefix = prefix
        self._sms_sender = sms_sender
        self.renderer = renderer

    def __str__(self):
        if self.values:
            return self.replaced
        return self.content

    def __repr__(self):
        return "{}(\"{}\", {})".format(self.__class__.__name__, self.content, self.values)  # TODO: more real

    @property
    def values(self):
        return self._values

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
    def renderer(self):
        return self._renderer

    @renderer.setter
    def renderer(self, value):
        if value:
            self._renderer = value
        elif self.template_type == 'sms':
            self._renderer = SMSPreview(
                prefix=self._prefix,
                sender=self._sms_sender
            )
        elif self.template_type == 'letter':
            self._renderer = LetterPreview(
                subject=self.subject
            )
        elif self.template_type == 'email' or not self.template_type:
            self._renderer = EmailPreview()

    def get_match(self, match):
        if match[1] and match[2]:
            return match[0]
        return match[0] + match[2]

    def format_match(self, match):
        if match.group(2) and match.group(3):
            return self.optional_placeholder_tag.format(match.group(1), match.group(3))
        return self.placeholder_tag.format(match.group(1), match.group(3))

    def replace_match(self, match):
        if match.group(2) and match.group(3):
            return strip_html(match.group(3)) if str2bool(self.values.get(match.group(1))) else ''
        return strip_html(self.values.get(match.group(1) + match.group(3)))

    @property
    def formatted(self):
        return self.renderer(re.sub(
            Template.placeholder_pattern, self.format_match, self.content
        ))

    @property
    def formatted_subject(self):
        return re.sub(
            Template.placeholder_pattern, self.format_match, self.subject
        )

    @property
    def formatted_subject_as_markup(self):
        return Markup(self.formatted_subject)

    @property
    def formatted_as_markup(self):
        return Markup(self.formatted)

    @property
    def placeholders(self):
        return OrderedSet(
            self.get_match(match) for match in re.findall(
                Template.placeholder_pattern, (self.subject or '') + self.content
            )
        )

    @property
    def replaced(self):
        if self.missing_data:
            raise NeededByTemplateError(self.missing_data)
        return self.renderer(re.sub(
            Template.placeholder_pattern, self.replace_match, self.content
        ))

    @property
    def replaced_content_count(self):
        return len(self.replaced.encode(self.encoding))

    @property
    def content_count(self):
        return len(self.content.encode(self.encoding))

    @property
    def sms_fragment_count(self):
        if self.template_type != 'sms':
            raise TypeError("The template needs to have a template type of 'sms'")
        return get_sms_fragment_count(self.replaced_content_count)

    @property
    def content_too_long(self):
        return (
            self.content_character_limit is not None and
            self.replaced_content_count > self.content_character_limit
        )

    @property
    def replaced_subject(self):
        if self.missing_data:
            raise NeededByTemplateError(self.missing_data)
        return re.sub(
            Template.placeholder_pattern,
            self.replace_match,
            self.subject if self.subject else ""
        )

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


class NeededByTemplateError(Exception):
    def __init__(self, keys):
        super(NeededByTemplateError, self).__init__(", ".join(keys))


class NoPlaceholderForDataError(Exception):
    def __init__(self, keys):
        super(NoPlaceholderForDataError, self).__init__(", ".join(keys))


class TemplateChange():

    def __init__(self, old_template, new_template):
        self.old_placeholders = Columns.from_keys(old_template.placeholders)
        self.new_placeholders = Columns.from_keys(new_template.placeholders)

    @property
    def has_different_placeholders(self):
        return bool(self.new_placeholders.keys() ^ self.old_placeholders.keys())

    @property
    def placeholders_added(self):
        return set(
            self.new_placeholders.get(key)
            for key in self.new_placeholders.keys() - self.old_placeholders.keys()
        )

    @property
    def placeholders_removed(self):
        return set(
            self.old_placeholders.get(key)
            for key in self.old_placeholders.keys() - self.new_placeholders.keys()
        )


def get_sms_fragment_count(character_count):
    return 1 if character_count <= 160 else math.ceil(float(character_count) / 153)


def str2bool(value):
    if not value:
        return False
    return str(value).lower() in ("yes", "y", "true", "t", "1", "include", "show")


def strip_html(value):
    return bleach.clean(value, tags=[], strip=True)
