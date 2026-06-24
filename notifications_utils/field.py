import re
from collections.abc import Callable, Mapping, Sequence, Set
from typing import Any, Literal, Self

from markupsafe import Markup

from notifications_utils.formatters import (
    escape_html,
    strip_and_remove_obscure_whitespace,
    unescaped_formatted_list,
)
from notifications_utils.insensitive_dict import InsensitiveDict, InsensitiveSet


class Placeholder:
    body: str

    def __init__(self, body: str):
        # body shouldn’t include leading/trailing brackets, like (( and ))
        self.body = body.lstrip("(").rstrip(")")

    @classmethod
    def from_match(cls, match: re.Match) -> Self:
        return cls(match.group(0))

    def is_conditional(self) -> bool:
        return "??" in self.body

    @property
    def name(self) -> str:
        # for non conditionals, name equals body
        return self.body.split("??")[0]

    @property
    def conditional_text(self) -> str:
        if self.is_conditional():
            # ((a?? b??c)) returns " b??c"
            return "??".join(self.body.split("??")[1:])
        else:
            raise ValueError(f"{self} not conditional")

    def get_conditional_body(self, show_conditional) -> str:
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

    placeholder_pattern: re.Pattern = re.compile(
        r"\({2}"  # opening ((
        r"([^()]+)"  # body of placeholder - potentially standard or conditional.
        r"\){2}"  # closing ))
    )
    placeholder_tag: str = "<span class='placeholder'>&#40;&#40;{}&#41;&#41;</span>"
    conditional_placeholder_tag: str = "<span class='placeholder-conditional'>&#40;&#40;{}??</span>{}&#41;&#41;"
    placeholder_tag_no_brackets: str = "<span class='placeholder-no-brackets'>{}</span>"
    placeholder_tag_redacted: str = "<span class='placeholder-redacted'>hidden</span>"

    content: str
    sanitizer: Callable[[str], str] | Callable[[str | None], str | None]
    markdown_lists: bool
    redact_missing_personalisation: bool

    _values: Mapping[str, Any]

    def __init__(
        self,
        content: str,
        values: Mapping[str, Any] | None = None,
        with_brackets: bool = True,
        html: Literal["escape", "passthrough"] = "escape",
        markdown_lists: bool = False,
        redact_missing_personalisation: bool = False,
    ):
        match html:
            case "escape":
                self.sanitizer = escape_html
            case "passthrough":
                self.sanitizer = str
            case _:
                raise TypeError(f"Unknown `html` value {html}")

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

    def splitlines(self) -> Sequence[str]:
        return str(self).splitlines()

    @property
    def values(self) -> Mapping[str, Any]:
        return self._values

    @values.setter
    def values(self, new_values: Mapping[str, Any] | None):
        self._values = InsensitiveDict({self.sanitizer(k): v for k, v in new_values.items()}) if new_values else {}

    def format_match(self, match: re.Match) -> str:
        return self.format_placeholder(Placeholder.from_match(match))

    def format_placeholder(self, placeholder: Placeholder) -> str:
        if self.redact_missing_personalisation:
            return self.placeholder_tag_redacted

        if placeholder.is_conditional():
            return self.conditional_placeholder_tag.format(placeholder.name, placeholder.conditional_text)

        return self.placeholder_tag.format(placeholder.name)

    def replace_match(self, match: re.Match) -> str:
        placeholder = Placeholder.from_match(match)
        replacement = self.get_replacement(placeholder)

        if replacement is None:
            return self.format_placeholder(placeholder)

        if placeholder.is_conditional():
            return placeholder.get_conditional_body(replacement)

        return replacement

    def get_replacement(self, placeholder: Placeholder) -> str | None:
        replacement = self.values.get(placeholder.name)
        if replacement is None:
            return None

        if isinstance(replacement, list):
            vals = list(
                filter(None, (strip_and_remove_obscure_whitespace(str(val)) for val in replacement if val is not None))
            )
            if not vals:
                return ""
            return self.sanitizer(self.get_replacement_as_list(vals))

        return self.sanitizer(str(replacement))

    def get_replacement_as_list(self, replacement: Sequence) -> str:
        if self.markdown_lists:
            return "\n\n" + "\n".join(f"* {item}" for item in replacement)
        return unescaped_formatted_list(replacement, before_each="", after_each="")

    @property
    def sanitized(self) -> str:
        return self.sanitizer(self.content) or ""

    @property
    def _raw_formatted(self) -> str:
        return re.sub(self.placeholder_pattern, self.format_match, self.sanitized)

    @property
    def formatted(self) -> str:
        return Markup(self._raw_formatted)

    @property
    def placeholders(self) -> Set[str]:
        if not self.content or "(" not in self.content:
            return InsensitiveSet()
        return InsensitiveSet(Placeholder(body).name for body in re.findall(self.placeholder_pattern, self.content))

    @property
    def replaced(self) -> str:
        return re.sub(self.placeholder_pattern, self.replace_match, self.sanitized)


class PlainTextField(Field):
    """
    Use this where no HTML should be rendered in the outputted content,
    even when no values have been passed in
    """

    placeholder_tag: str = "(({}))"
    conditional_placeholder_tag: str = "(({}??{}))"
    placeholder_tag_no_brackets: str = "{}"
    placeholder_tag_redacted: str = "[hidden]"


def str2bool(value) -> bool:
    if not value:
        return False
    return str(value).lower() in ("yes", "y", "true", "t", "1", "include", "show")
