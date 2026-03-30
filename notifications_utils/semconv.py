from collections.abc import MutableMapping
from sys import exception

from opentelemetry.util.types import AttributeValue

# Buckets ranging from milliseconds to 30 minutes,
# suitable for e.g. Celery task durations
TASK_DURATION_HISTOGRAM_BUCKETS = [
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.0,
    4.0,
    8.0,
    15.0,
    30.0,
    60.0,
    120.0,
    240.0,
    480.0,
    900.0,
    1800.0,
]


def set_error_type(attributes: MutableMapping[str, AttributeValue]) -> None:
    """
    Sets key `"error.type"` in `attributes` to the fully-qualified name of the current exception, if any.
    """
    e = exception()
    if e is not None:
        attributes["error.type"] = type(e).__module__ + "." + type(e).__qualname__
