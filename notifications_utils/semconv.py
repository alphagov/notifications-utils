import os
from collections.abc import MutableMapping
from sys import exception
from uuid import uuid4

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

# Buckets suitable for HTTP request durations.
# Copied from opentelemetry.instrumentation._semconv.HTTP_DURATION_HISTOGRAM_BUCKETS_NEW.
HTTP_DURATION_HISTOGRAM_BUCKETS = [
    0.005,
    0.01,
    0.025,
    0.05,
    0.075,
    0.1,
    0.25,
    0.5,
    0.75,
    1,
    2.5,
    5,
    7.5,
    10,
]


def set_error_type(attributes: MutableMapping[str, AttributeValue]) -> None:
    """
    Sets key `"error.type"` in `attributes` to the fully-qualified name of the current exception, if any.
    """
    e = exception()
    if e is not None:
        attributes["error.type"] = type(e).__module__ + "." + type(e).__qualname__


def set_service_instance_id() -> None:
    """Updates the `OTEL_RESOURCE_ATTRIBUTES` environment variable to set `service.instance.id` to a random UUIDv4.

    For applications that use fork-based concurrency (which includes both Celery and Gunicorn), this should be called
    in a post-fork hook, before the call to `opentelemetry.instrumentation.auto_instrumentation.initialize()`, to
    ensure that each worker process gets a unique service instance ID.

    Future versions of opentelemetry-python might do this automatically, in which case we can remove this.

    See also:
        https://github.com/open-telemetry/opentelemetry-python/issues/4390
        https://opentelemetry.io/docs/specs/semconv/registry/attributes/service/
    """
    old_value = os.environ.get("OTEL_RESOURCE_ATTRIBUTES")
    new_value = f"service.instance.id={uuid4()}"
    os.environ["OTEL_RESOURCE_ATTRIBUTES"] = f"{old_value},{new_value}" if old_value is not None else new_value
