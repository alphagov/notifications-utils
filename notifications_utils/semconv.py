from collections.abc import MutableMapping
from sys import exception

from opentelemetry.util.types import AttributeValue


def set_error_type(attributes: MutableMapping[str, AttributeValue]) -> None:
    """
    Sets key `"error.type"` in `attributes` to the fully-qualified name of the current exception, if any.
    """
    e = exception()
    if e is not None:
        attributes["error.type"] = type(e).__module__ + "." + type(e).__qualname__
