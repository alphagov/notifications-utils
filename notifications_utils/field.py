import re

from markupsafe import Markup
from ordered_set import OrderedSet

from notifications_utils.formatters import (
    escape_html,
    strip_and_remove_obscure_whitespace,
    unescaped_formatted_list,
)
from notifications_utils.insensitive_dict import InsensitiveDict


class Placeholder:
    def __new__(cls, body, field=None):
        class_ = super().__new__(cls)

        if field and field.redact_missing_personalisation:
            class_.__class__ = RedactedPlaceholder

        if "??" in body:
            class_.__class__ = ConditionalPlaceholder

        if field and not field.with_brackets:
            class_.__class__ = NoBracketsPlaceholder

        return class_

    def __init__(self, body, field=None):
        # body shouldn’t include leading/trailing brackets, like (( and ))
        self.body = body.lstrip("(").rstrip(")")

    @property
    def name(self):
        return self.body

    @classmethod
    def from_match_and_field(cls, match, field):
        return cls(match.group(0), field)

    def __repr__(self):
        return f"{self.__class__.__name__}({self.body})"

    def format(self):
        return f"<span class='placeholder'>&#40;&#40;{self.name}&#41;&#41;</span>"

    def replace_with(self, replacement):
        if replacement is None:
            return self.format()
        return replacement


class RedactedPlaceholder(Placeholder):
    def format(self):
        return "<span class='placeholder-redacted'>hidden</span>"


class NoBracketsPlaceholder(Placeholder):
    def format(self):
        return f"<span class='placeholder-no-brackets'>{self.name}</span>"


class ConditionalPlaceholder(Placeholder):
    @property
    def name(self):
        # for non conditionals, name equals body
        return self.body.split("??")[0]

    @property
    def conditional_text(self):
        return "??".join(self.body.split("??")[1:])

    def get_conditional_body(self, show_conditional):
        return self.conditional_text if str2bool(show_conditional) else ""

    def format(self):
        return f"<span class='placeholder-conditional'>&#40;&#40;{self.name}??</span>{self.conditional_text}&#41;&#41;"

    def replace_with(self, replacement):
        if replacement is None:
            return self.format()
        return self.get_conditional_body(replacement)


class Field:
    """
    An instance of Field represents a string of text which may contain
    placeholders.

    If values are provided the field replaces the placeholders with the
    corresponding values. If a value for a placeholder is missing then
    the field will highlight the placeholder by wrapping it in some HTML.

    A template can have several fields, for example an email template
    has a field for the body and a field for the subject.
    """

    placeholder_pattern = re.compile(
        r"\({2}"  # opening ((
        r"([^()]+)"  # body of placeholder - potentially standard or conditional.
        r"\){2}"  # closing ))
    )

    def __init__(
        self,
        content,
        values=None,
        with_brackets=True,
        html="escape",
        markdown_lists=False,
        redact_missing_personalisation=False,
    ):
        self.sanitizer = {
            "escape": escape_html,
            "passthrough": str,
        }[html]
        self.content = content
        self.values = values
        self.markdown_lists = markdown_lists
        self.redact_missing_personalisation = redact_missing_personalisation
        self.with_brackets = with_brackets

    def __str__(self):
        if self.values:
            return self.replaced
        return self.formatted

    def __repr__(self):
        return f'{self.__class__.__name__}("{self.content}", {self.values})'

    def splitlines(self):
        return str(self).splitlines()

    @property
    def values(self):
        return self._values

    @values.setter
    def values(self, value):
        self._values = InsensitiveDict({self.sanitizer(k): value[k] for k in value}) if value else {}

    def format_match(self, match):
        return Placeholder.from_match_and_field(match, self).format()

    def replace_match(self, match):
        placeholder = Placeholder.from_match_and_field(match, self)
        replacement = self.get_replacement(placeholder)
        return placeholder.replace_with(replacement)

    def get_replacement(self, placeholder):
        replacement = self.values.get(placeholder.name)
        if replacement is None:
            return None

        if isinstance(replacement, list):
            vals = (strip_and_remove_obscure_whitespace(str(val)) for val in replacement if val is not None)
            vals = list(filter(None, vals))
            if not vals:
                return ""
            return self.sanitizer(self.get_replacement_as_list(vals))

        return self.sanitizer(str(replacement))

    def get_replacement_as_list(self, replacement):
        if self.markdown_lists:
            return "\n\n" + "\n".join(f"* {item}" for item in replacement)
        return unescaped_formatted_list(replacement, before_each="", after_each="")

    @property
    def _raw_formatted(self):
        return re.sub(self.placeholder_pattern, self.format_match, self.sanitizer(self.content))

    @property
    def formatted(self):
        return Markup(self._raw_formatted)

    @property
    def placeholders(self):
        if not getattr(self, "content", ""):
            return set()
        return OrderedSet(Placeholder(body).name for body in re.findall(self.placeholder_pattern, self.content))

    @property
    def replaced(self):
        return re.sub(self.placeholder_pattern, self.replace_match, self.sanitizer(self.content))


class PlainTextField(Field):
    """
    Use this where no HTML should be rendered in the outputted content,
    even when no values have been passed in
    """

    placeholder_tag = "(({}))"
    conditional_placeholder_tag = "(({}??{}))"
    placeholder_tag_no_brackets = "{}"
    placeholder_tag_redacted = "[hidden]"


def str2bool(value):
    if not value:
        return False
    return str(value).lower() in ("yes", "y", "true", "t", "1", "include", "show")
