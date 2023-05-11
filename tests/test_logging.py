import json
import logging as builtin_logging
import logging.handlers as builtin_logging_handlers

import pytest

from notifications_utils import logging


def test_get_handlers_sets_up_logging_appropriately_with_debug(tmpdir):
    class App:
        config = {"NOTIFY_LOG_PATH": str(tmpdir / "foo"), "NOTIFY_APP_NAME": "bar", "NOTIFY_LOG_LEVEL": "ERROR"}
        debug = True

    app = App()

    handlers = logging.get_handlers(app, extra_filters=[])

    assert len(handlers) == 1
    assert type(handlers[0]) == builtin_logging.StreamHandler
    assert type(handlers[0].formatter) == builtin_logging.Formatter
    assert not (tmpdir / "foo").exists()


@pytest.mark.parametrize(
    "platform",
    [
        "local",
        "paas",
        "something-else",
    ],
)
def test_get_handlers_sets_up_logging_appropriately_without_debug_when_not_on_ecs(tmpdir, platform):
    class TestFilter(builtin_logging.Filter):
        def filter(self, record):
            record.arbitrary_info = "some-extra-info"
            return record

    class App:
        config = {
            # make a tempfile called foo
            "NOTIFY_LOG_PATH": str(tmpdir / "foo"),
            "NOTIFY_APP_NAME": "bar",
            "NOTIFY_LOG_LEVEL": "ERROR",
            "NOTIFY_RUNTIME_PLATFORM": platform,
        }
        debug = False

    app = App()

    handlers = logging.get_handlers(app, extra_filters=[TestFilter()])

    assert len(handlers) == 2
    assert type(handlers[0]) == builtin_logging.StreamHandler
    assert type(handlers[0].formatter) == logging.JSONFormatter
    assert len(handlers[0].filters) == 5

    assert type(handlers[1]) == builtin_logging_handlers.WatchedFileHandler
    assert type(handlers[1].formatter) == logging.JSONFormatter
    assert len(handlers[1].filters) == 5

    dir_contents = tmpdir.listdir()
    assert len(dir_contents) == 1
    assert dir_contents[0].basename == "foo.json"


def test_get_handlers_sets_up_logging_appropriately_without_debug_on_ecs(tmpdir):
    class App:
        config = {
            # make a tempfile called foo
            "NOTIFY_LOG_PATH": str(tmpdir / "foo"),
            "NOTIFY_APP_NAME": "bar",
            "NOTIFY_LOG_LEVEL": "ERROR",
            "NOTIFY_RUNTIME_PLATFORM": "ecs",
        }
        debug = False

    app = App()

    handlers = logging.get_handlers(app, extra_filters=[])

    assert len(handlers) == 1
    assert type(handlers[0]) == builtin_logging.StreamHandler
    assert type(handlers[0].formatter) == logging.JSONFormatter

    assert not (tmpdir / "foo.json").exists()


def test_base_json_formatter_contains_service_id(tmpdir):
    record = builtin_logging.LogRecord(
        name="log thing", level="info", pathname="path", lineno=123, msg="message to log", exc_info=None, args=None
    )

    service_id_filter = logging.ServiceIdFilter()
    assert json.loads(logging.BaseJSONFormatter().format(record))["message"] == "message to log"
    assert service_id_filter.filter(record).service_id == "no-service-id"
