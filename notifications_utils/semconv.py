import os
from collections import deque
from collections.abc import Callable, Iterable, MutableMapping
from sys import exception
from typing import Any
from uuid import uuid4

import flask
from opentelemetry.metrics import CallbackOptions, Observation
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


_oneshot_gauge_next_observations_consumer_strong_refs: list[Callable[[CallbackOptions], Iterable[Observation]]] = []


def oneshot_gauge_next_observations_consumer(
    next_observations_deque: deque[Observation],
) -> Callable[[CallbackOptions], Iterable[Observation]]:
    """
    Returns a function that, when called with `CallbackOptions`, will consumer the contents of
    `next_observations_deque`, deduplicate them by their attributes and return the last for each
    attribute-set.

    This is intended for use as a callback with an ObservableGauge to make it act like an old-style "one-shot"
    asynchronous gauge - a gauge that will *not* output its most recent value indefinitely (like
    synchronous gauges do in opentelemetry-sdk >= 1.45), instead stopping after the first collection period
    that doesn't contain an Observation for a particular time-series (like synchronous gauges did in
    opentelemetry-sdk < 1.45).

    Metric recording functions are expected to append their `Observation`s to the next_observations_deque
    for a particular metric and trust the opentelemetry collection loop to consume the queue on its next
    cycle.
    """

    def _oneshot_consumer(opts: CallbackOptions) -> Iterable[Observation]:
        observations_dedup_map: dict[Any, Observation] = {}
        while next_observations_deque:
            try:
                # deque.popleft() is allegedly atomic
                observation = next_observations_deque.popleft()
            except IndexError:
                # could something else have popped the last value since we checked for emptiness?
                # anyway nothing left
                break
            else:
                # callbacks must not return observations with duplicate attrs in one collection cycle, so
                # deduplicate with later observations always taking priority
                dedup_key = (
                    tuple(sorted(str(x) for x in observation.attributes.items())) if observation.attributes else ()
                )
                observations_dedup_map[dedup_key] = observation

        return observations_dedup_map.values()

    # opentelemetry-sdk really likes using weakrefs. we need to ensure our callback doesn't get
    # garbage collected.
    _oneshot_gauge_next_observations_consumer_strong_refs.append(_oneshot_consumer)
    # but let's give us a chance of noticing if it gets excessive (but don't spam the logs)
    strong_ref_count = len(_oneshot_gauge_next_observations_consumer_strong_refs)
    if strong_ref_count >= 1_000 and strong_ref_count % 1_000 == 0 and flask.has_app_context():
        extra = {"strong_ref_count": strong_ref_count}
        flask.current_app.logger.warning(
            "oneshot_gauge_next_observations_consumer is holding %(strong_ref_count)s strong refs - "
            "this is probably not intentional",
            extra,
            extra=extra,
        )

    return _oneshot_consumer
