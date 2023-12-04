import json
import logging as builtin_logging
import logging.handlers as builtin_logging_handlers
import time
from unittest import mock

import pytest

from notifications_utils import logging
from notifications_utils.testing.comparisons import RestrictedAny


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


@pytest.mark.parametrize(
    "status_code,expected_after_level",
    (
        (200, builtin_logging.INFO),
        (201, builtin_logging.INFO),
        (400, builtin_logging.INFO),
        (503, builtin_logging.WARNING),
    ),
)
def test_app_request_logs_level_by_status_code(
    app_with_mocked_logger,
    status_code,
    expected_after_level,
):
    app = app_with_mocked_logger
    mock_req_logger = mock.Mock(
        spec=builtin_logging.Logger("flask.app.request"),
        handlers=[],
    )
    app.logger.getChild.side_effect = lambda name: mock_req_logger if name == "request" else mock.DEFAULT

    logging.init_app(app)

    @app.route("/")
    def some_route():
        time.sleep(0.05)
        return "foo", status_code

    app.test_client().get("/")

    assert (
        mock.call(
            builtin_logging.DEBUG,
            "Received request %(method)s %(url)s",
            {
                "url": "http://localhost/",
                "method": "GET",
                "endpoint": "some_route",
                "process_": RestrictedAny(lambda value: isinstance(value, int)),
            },
            extra={
                "url": "http://localhost/",
                "method": "GET",
                "endpoint": "some_route",
                "process_": RestrictedAny(lambda value: isinstance(value, int)),
            },
        )
        in mock_req_logger.log.call_args_list
    )

    assert (
        mock.call(
            expected_after_level,
            "%(method)s %(url)s %(status)s took %(request_time)ss",
            {
                "url": "http://localhost/",
                "method": "GET",
                "endpoint": "some_route",
                "status": status_code,
                "request_time": RestrictedAny(lambda value: isinstance(value, float) and 0.05 <= value),
                "process_": RestrictedAny(lambda value: isinstance(value, int)),
            },
            extra={
                "url": "http://localhost/",
                "method": "GET",
                "endpoint": "some_route",
                "status": status_code,
                "request_time": RestrictedAny(lambda value: isinstance(value, float) and 0.05 <= value),
                "process_": RestrictedAny(lambda value: isinstance(value, int)),
            },
        )
        in mock_req_logger.log.call_args_list
    )


def test_app_request_logs_responses_on_exception(app_with_mocked_logger):
    app = app_with_mocked_logger
    mock_req_logger = mock.Mock(
        spec=builtin_logging.Logger("flask.app.request"),
        handlers=[],
    )
    app.logger.getChild.side_effect = lambda name: mock_req_logger if name == "request" else mock.DEFAULT

    logging.init_app(app)

    @app.route("/")
    def some_route():
        time.sleep(0.05)
        raise Exception("oh no")

    app.test_client().get("/")

    assert (
        mock.call(
            builtin_logging.DEBUG,
            "Received request %(method)s %(url)s",
            {
                "url": "http://localhost/",
                "method": "GET",
                "endpoint": "some_route",
                "process_": RestrictedAny(lambda value: isinstance(value, int)),
            },
            extra={
                "url": "http://localhost/",
                "method": "GET",
                "endpoint": "some_route",
                "process_": RestrictedAny(lambda value: isinstance(value, int)),
            },
        )
        in mock_req_logger.log.call_args_list
    )

    assert (
        mock.call(
            builtin_logging.WARNING,
            "%(method)s %(url)s %(status)s took %(request_time)ss",
            {
                "url": "http://localhost/",
                "method": "GET",
                "endpoint": "some_route",
                "status": 500,
                "request_time": RestrictedAny(lambda value: isinstance(value, float) and 0.05 <= value),
                "process_": RestrictedAny(lambda value: isinstance(value, int)),
            },
            extra={
                "url": "http://localhost/",
                "method": "GET",
                "endpoint": "some_route",
                "status": 500,
                "request_time": RestrictedAny(lambda value: isinstance(value, float) and 0.05 <= value),
                "process_": RestrictedAny(lambda value: isinstance(value, int)),
            },
        )
        in mock_req_logger.log.call_args_list
    )


def test_app_request_logs_responses_on_unknown_route(app_with_mocked_logger):
    app = app_with_mocked_logger
    mock_req_logger = mock.Mock(
        spec=builtin_logging.Logger("flask.app.request"),
        handlers=[],
    )
    app.logger.getChild.side_effect = lambda name: mock_req_logger if name == "request" else mock.DEFAULT

    logging.init_app(app)

    app.test_client().get("/foo")

    assert (
        mock.call(
            builtin_logging.DEBUG,
            "Received request %(method)s %(url)s",
            {
                "url": "http://localhost/foo",
                "method": "GET",
                "endpoint": None,
                "process_": RestrictedAny(lambda value: isinstance(value, int)),
            },
            extra={
                "url": "http://localhost/foo",
                "method": "GET",
                "endpoint": None,
                "process_": RestrictedAny(lambda value: isinstance(value, int)),
            },
        )
        in mock_req_logger.log.call_args_list
    )

    assert (
        mock.call(
            builtin_logging.INFO,
            "%(method)s %(url)s %(status)s took %(request_time)ss",
            {
                "url": "http://localhost/foo",
                "method": "GET",
                "endpoint": None,
                "status": 404,
                "request_time": RestrictedAny(lambda value: isinstance(value, float)),
                "process_": RestrictedAny(lambda value: isinstance(value, int)),
            },
            extra={
                "url": "http://localhost/foo",
                "method": "GET",
                "endpoint": None,
                "status": 404,
                "request_time": RestrictedAny(lambda value: isinstance(value, float)),
                "process_": RestrictedAny(lambda value: isinstance(value, int)),
            },
        )
        in mock_req_logger.log.call_args_list
    )


@pytest.mark.parametrize(
    "level_name,expected_level",
    (
        ("INFO", builtin_logging.INFO),
        ("WARNING", builtin_logging.WARNING),
    ),
)
def test_app_request_logger_level_set(app_with_mocked_logger, level_name, expected_level):
    app = app_with_mocked_logger
    mock_req_logger = mock.Mock(
        spec=builtin_logging.Logger("flask.app.request"),
        handlers=[],
    )
    app.logger.getChild.side_effect = lambda name: mock_req_logger if name == "request" else mock.DEFAULT

    app.config["NOTIFY_REQUEST_LOG_LEVEL"] = level_name
    logging.init_app(app)

    assert mock_req_logger.setLevel.call_args_list[-1] == mock.call(expected_level)


@pytest.mark.parametrize(
    "rtplatform,expected_level",
    (
        ("ecs", builtin_logging.NOTSET),
        ("local", builtin_logging.NOTSET),
        ("paas", builtin_logging.CRITICAL),
    ),
)
def test_app_request_logger_level_defaults(app_with_mocked_logger, rtplatform, expected_level):
    app = app_with_mocked_logger
    mock_req_logger = mock.Mock(
        spec=builtin_logging.Logger("flask.app.request"),
        handlers=[],
    )
    app.logger.getChild.side_effect = lambda name: mock_req_logger if name == "request" else mock.DEFAULT

    app.config["NOTIFY_RUNTIME_PLATFORM"] = rtplatform
    logging.init_app(app)

    assert mock_req_logger.setLevel.call_args_list[-1] == mock.call(expected_level)
