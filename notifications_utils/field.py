import re
from enum import StrEnum, auto

from markupsafe import Markup
from ordered_set import OrderedSet

from notifications_utils.formatters import (
    escape_html,
    strip_and_remove_obscure_whitespace,
    unescaped_formatted_list,
)
from notifications_utils.insensitive_dict import InsensitiveDict


class Placeholder:
    def __init__(self, body):
        # body shouldn’t include leading/trailing brackets, like (( and ))
        self.body = body.lstrip("(").rstrip(")")

    class Types(StrEnum):
        BASE = auto()
        UNSAFE = auto()
        CONDITIONAL = auto()

    # order matters as the placeholder type will be the first type that returns a match
    # conditional shoud come first because no escaping should happen on conditional
    # placeholders as they don't contain vulnerable input
    extended_type_pattern = {
        Types.CONDITIONAL: re.compile(r".*\?\?.*"),
        Types.UNSAFE: re.compile(r".*::unsafe$"),
    }

    @property
    def type(self):
        for type, pattern in self.extended_type_pattern.items():
            if re.match(pattern, self.body):
                return type
        return self.Types.BASE

    @classmethod
    def from_match(cls, match):
        return cls(match.group(0))

    def is_conditional(self):
        return self.type == self.Types.CONDITIONAL

    def is_unsafe(self):
        return self.type == self.Types.UNSAFE

    @property
    def name(self):
        # for non conditionals, name equals body
        match self.type:
            case self.Types.BASE:
                return self.body
            case self.Types.UNSAFE:
                return self.body.split("::unsafe")[0]
            case self.Types.CONDITIONAL:
                return self.body.split("??")[0]

    @property
    def conditional_text(self):
        if self.is_conditional():
            # ((a?? b??c)) returns " b??c"
            return "??".join(self.body.split("??")[1:])
        else:
            raise ValueError(f"{self} not conditional")

    def get_conditional_body(self, show_conditional):
        # note: unsanitised/converted
        if self.is_conditional():
            return self.conditional_text if str2bool(show_conditional) else ""
        else:
            raise ValueError(f"{self} not conditional")

    def __repr__(self):
        return f"Placeholder({self.body})"


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
    placeholder_tag = "<span class='placeholder'>&#40;&#40;{}&#41;&#41;</span>"
    conditional_placeholder_tag = "<span class='placeholder-conditional'>&#40;&#40;{}??</span>{}&#41;&#41;"
    placeholder_tag_no_brackets = "<span class='placeholder-no-brackets'>{}</span>"
    placeholder_tag_redacted = "<span class='placeholder-redacted'>hidden</span>"
    placeholder_tag_unsafe = "<span class='placeholder'>&#40;&#40;{}</span>::unsafe&#41;&#41;"

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
        if not with_brackets:
            self.placeholder_tag = self.placeholder_tag_no_brackets
        self.redact_missing_personalisation = redact_missing_personalisation

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
        return self.format_placeholder(Placeholder.from_match(match))

    def format_placeholder(self, placeholder):
        if self.redact_missing_personalisation:
            return self.placeholder_tag_redacted

        if placeholder.is_conditional():
            return self.conditional_placeholder_tag.format(placeholder.name, placeholder.conditional_text)

        if placeholder.is_unsafe():
            return self.placeholder_tag_unsafe.format(placeholder.name)

        return self.placeholder_tag.format(placeholder.name)

    def replace_match(self, match):
        placeholder = Placeholder.from_match(match)
        replacement = self.get_replacement(placeholder)

        if replacement is None:
            return self.format_placeholder(placeholder)

        if placeholder.is_conditional():
            return placeholder.get_conditional_body(replacement)

        if placeholder.is_unsafe():
            return "SANITISED"

        return replacement

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
    placeholder_tag_unsafe = "(({}::unsafe))"


def str2bool(value):
    if not value:
        return False
    return str(value).lower() in ("yes", "y", "true", "t", "1", "include", "show")
