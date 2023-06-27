import logging
from unittest.mock import ANY, Mock

from notifications_utils.statsd_decorators import statsd


class AnyStringWith(str):
    def __eq__(self, other):
        return self in other


def test_should_call_statsd(app, caplog):
    app.config["NOTIFY_ENVIRONMENT"] = "test"
    app.config["NOTIFY_APP_NAME"] = "api"
    app.config["STATSD_HOST"] = "localhost"
    app.config["STATSD_PORT"] = "8000"
    app.config["STATSD_PREFIX"] = "prefix"
    app.statsd_client = Mock()

    @statsd(namespace="test")
    def test_function():
        return True

    with caplog.at_level(logging.DEBUG):
        assert test_function()

    assert AnyStringWith("test call test_function took ") in caplog.messages
    app.statsd_client.incr.assert_called_once_with("test.test_function")
    app.statsd_client.timing.assert_called_once_with("test.test_function", ANY)
