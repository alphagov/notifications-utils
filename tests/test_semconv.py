import logging
import os
from collections import deque

import pytest
from opentelemetry.metrics import Observation
from opentelemetry.util.types import AttributeValue
from pytest_mock import MockerFixture

from notifications_utils.semconv import (
    oneshot_gauge_next_observations_consumer,
    set_error_type,
    set_service_instance_id,
)


class MyException(Exception):
    pass


def test_set_error_type_without_exception() -> None:
    try:
        pass
    finally:
        attributes: dict[str, AttributeValue] = {"foo.bar": "baz"}
        set_error_type(attributes)
        assert attributes == {"foo.bar": "baz"}


def test_set_error_type_with_exception() -> None:
    with pytest.raises(MyException):
        try:
            raise MyException
        finally:
            attributes: dict[str, AttributeValue] = {"foo.bar": "baz"}
            set_error_type(attributes)
            assert attributes == {
                "foo.bar": "baz",
                "error.type": "tests.test_semconv.MyException",
            }


def test_set_service_instance_id(mocker: MockerFixture) -> None:
    mocker.patch("notifications_utils.semconv.uuid4", return_value="00000000-0000-0000-0000-000000000000")
    set_service_instance_id()
    assert os.environ["OTEL_RESOURCE_ATTRIBUTES"] == "service.instance.id=00000000-0000-0000-0000-000000000000"


def test_set_service_instance_id_retains_existing_resource_attributes(mocker: MockerFixture) -> None:
    mocker.patch("notifications_utils.semconv.uuid4", return_value="00000000-0000-0000-0000-000000000000")
    os.environ["OTEL_RESOURCE_ATTRIBUTES"] = "foo=bar"
    set_service_instance_id()
    assert os.environ["OTEL_RESOURCE_ATTRIBUTES"] == "foo=bar,service.instance.id=00000000-0000-0000-0000-000000000000"


@pytest.mark.parametrize(
    "observations_in,expected_observations_out",
    (
        (
            (),
            (),
        ),
        (
            (Observation(1.0, {"foo": "bar", "baz": 123}),),
            (Observation(1.0, {"foo": "bar", "baz": 123}),),
        ),
        (
            (
                Observation(1.0, {"foo": "bar", "baz": 123}),
                Observation(2.0, {"foo": "321", "baz": None}),
            ),
            (
                Observation(1.0, {"foo": "bar", "baz": 123}),
                Observation(2.0, {"foo": "321", "baz": None}),
            ),
        ),
        (
            (
                Observation(1.0, None),
                Observation(2.0, {"foo": "bar"}),
                Observation(3.0, {"foo": "bar", "qux": 88}),
                Observation(4.0, {"foo": "bar", "qux": 99}),
                Observation(5.0, {"foo": "bar", "qux": 88}),
                Observation(6.0, {"foo": "bar"}),
                Observation(7.0, None),
            ),
            (
                Observation(4.0, {"foo": "bar", "qux": 99}),
                Observation(5.0, {"foo": "bar", "qux": 88}),
                Observation(6.0, {"foo": "bar"}),
                Observation(7.0, None),
            ),
        ),
        (
            (
                Observation(999.0, {"baz": 123}),
                Observation(1.0, {"baz": 123}),
            ),
            (Observation(1.0, {"baz": 123}),),
        ),
    ),
)
def test_oneshot_gauge_next_observations_consumer(observations_in, expected_observations_out, mocker):
    strong_refs = []
    mocker.patch("notifications_utils.semconv._oneshot_gauge_next_observations_consumer_strong_refs", new=strong_refs)

    test_deque = deque()
    test_consumer = oneshot_gauge_next_observations_consumer(test_deque)

    assert strong_refs == [test_consumer]

    test_deque.extend(observations_in)

    assert sorted(
        test_consumer(mocker.Mock()),
        key=lambda obs: tuple(sorted(str(x) for x in obs.attributes.items()) if obs.attributes else ()),
    ) == sorted(
        expected_observations_out,
        key=lambda obs: tuple(sorted(str(x) for x in obs.attributes.items()) if obs.attributes else ()),
    )

    assert len(test_deque) == 0


def test_oneshot_gauge_next_observations_consumer_logs_warning(caplog, app, mocker):
    strong_refs = []
    mocker.patch("notifications_utils.semconv._oneshot_gauge_next_observations_consumer_strong_refs", new=strong_refs)

    with caplog.at_level(logging.WARNING), app.app_context():
        for _ in range(2345):
            oneshot_gauge_next_observations_consumer(deque())

        assert caplog.messages == [
            "oneshot_gauge_next_observations_consumer is holding 1000 strong refs - this is probably not intentional",
            "oneshot_gauge_next_observations_consumer is holding 2000 strong refs - this is probably not intentional",
        ]

    assert len(strong_refs) == 2345


def test_oneshot_gauge_next_observations_consumer_no_app_logs_no_warning(caplog, mocker):
    strong_refs = []
    mocker.patch("notifications_utils.semconv._oneshot_gauge_next_observations_consumer_strong_refs", new=strong_refs)

    with caplog.at_level(logging.WARNING):
        for _ in range(2345):
            oneshot_gauge_next_observations_consumer(deque())

        assert caplog.messages == []

    assert len(strong_refs) == 2345
