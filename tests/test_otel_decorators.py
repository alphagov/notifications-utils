import logging
from unittest.mock import ANY, Mock

from notifications_utils.otel_decorators import otel


class AnyStringWith(str):
    def __eq__(self, other):
        return self in other


def test_should_call_otel(app, caplog):
    app.otel_client = Mock()

    @otel(namespace="test")
    def test_function():
        return True

    with caplog.at_level(logging.DEBUG):
        assert test_function()

    assert AnyStringWith("test call test_function took ") in caplog.messages
    app.otel_client.incr.assert_called_once_with(
        "function_call_test_test_function",
        value=1,
        description="Function call count",
    )
    app.otel_client.record.assert_called_once_with(
        "function_duration_test_test_function",
        ANY,
        description="Duration of function in seconds",
        unit="seconds",
        explicit_bucket_boundaries_advisory=[
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
        ],
    )
