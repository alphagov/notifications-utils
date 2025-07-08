import time
from collections.abc import Callable
from contextlib import AbstractContextManager, contextmanager
from functools import wraps
from typing import Any

from opentelemetry.metrics import get_meter
from opentelemetry.trace import Span, Status, StatusCode, Tracer

default_histogram_bucket = [
    0.005,
    0.01,
    0.025,
    0.05,
    0.075,
    0.1,
    0.25,
    0.5,
    0.75,
    1.0,
    2.5,
    5.0,
    7.5,
    10.0,
    float("inf"),
]

# Examples of how to use the otel_duration_histogram decorator:

# Example 1: Static attributes (current behavior)
# @otel_duration_histogram("my_function_duration", attributes={"operation": "send_email"})
# def send_email(to, subject):
#     ...

# Example 2: Dynamic attributes based on function arguments
# @otel_duration_histogram("process_user_duration", attributes=lambda args, kwargs: {"user_id": kwargs.get("user_id")})
# def process_user(user_id):
#     ...

# Example 3: Dynamic attributes using both args and kwargs
# @otel_duration_histogram("do_something_duration", attributes=lambda args, kwargs: {
#     "first_arg": args[0] if args else None,
#     "keyword": kwargs.get("keyword")
# })
# def do_something(a, keyword=None):
#     ...

# If you are considering using this decorator, think about if a span would be more appropriate for your use case.
# If we are using spanmetrics inside the otel collector you will automatically get a histogram for the span duration.


def otel_duration_histogram(
    name: str,
    *,
    unit: str = "seconds",
    description: str = "",
    attributes: dict[str, Any] | Callable[[tuple, dict], dict[str, Any]] | None = None,
):
    """
    Decorator to record function execution time in an OpenTelemetry histogram.

    Args:
        name (str): Name of the histogram metric.
        unit (str): Unit of measurement (default: "seconds").
        description (str): Description of the metric.
        attributes (dict or callable, optional): Static or dynamic attributes.

    Returns:
        function: Wrapped function with histogram instrumentation.
    """
    meter = get_meter(__name__)
    histogram = meter.create_histogram(name, unit=unit, description=description)

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            status = "success"
            try:
                return func(*args, **kwargs)
            except Exception:
                status = "error"
                raise
            finally:
                elapsed = time.perf_counter() - start
                base_attrs = attributes(args, kwargs) if callable(attributes) else (attributes or {})
                record_attrs = {**base_attrs, "status": status}
                histogram.record(elapsed, attributes=record_attrs)

        return wrapper

    return decorator


@contextmanager
def otel_span_with_status(tracer: Tracer, name: str, **attributes: Any) -> AbstractContextManager[Span]:
    """
    Context manager to create an OpenTelemetry span with status handling.

    Args:
        tracer: The tracer instance.
        name (str): Name of the span.
        **attributes: Attributes to set on the span.

    Yields:
        span: The created span.
    """
    with tracer.start_as_current_span(name) as span:
        for key, value in attributes.items():
            span.set_attribute(key, value)
        try:
            yield span
        except Exception as exc:
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            raise
