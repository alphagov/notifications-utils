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
        "function_call",
        value=1,
        attributes={
            "function": "test_function",
            "namespace": "test",
        },
        description="Function call count",
    )
    app.otel_client.record.assert_called_once_with(
        "function_duration_seconds",
        ANY,
        attributes={
            "function": "test_function",
            "namespace": "test",
        },
        description="Duration of function in seconds",
        unit="seconds",
    )
