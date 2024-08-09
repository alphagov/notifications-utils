import json
import logging as builtin_logging
import time
from unittest import mock

import pytest
from freezegun import freeze_time

from notifications_utils import logging, request_helper
from notifications_utils.testing.comparisons import AnyStringMatching, RestrictedAny


def test_get_handlers_sets_up_logging_appropriately_with_debug():
    class App:
        config = {"NOTIFY_APP_NAME": "bar", "NOTIFY_LOG_LEVEL": "ERROR"}
        debug = True

    app = App()

    handlers = logging.get_handlers(app, extra_filters=[])

    assert len(handlers) == 1
    assert type(handlers[0]) is builtin_logging.StreamHandler
    assert type(handlers[0].formatter) is logging.Formatter


def test_get_handlers_sets_up_logging_appropriately_without_debug():
    class App:
        config = {
            "NOTIFY_APP_NAME": "bar",
            "NOTIFY_LOG_LEVEL": "ERROR",
        }
        debug = False

    app = App()

    handlers = logging.get_handlers(app, extra_filters=[])

    assert len(handlers) == 1
    assert type(handlers[0]) is builtin_logging.StreamHandler
    assert type(handlers[0].formatter) is logging.JSONFormatter


@pytest.mark.parametrize(
    "frozen_time,logged_time",
    [
        ("2023-10-31 00:00:01.12345678", "2023-10-31T00:00:01.123456"),
        ("2020-01-15 01:01:02.999999999", "2020-01-15T01:01:02.999999"),
        ("2020-11-18 12:12:12.000000", "2020-11-18T12:12:12.000000"),
    ],
)
def test_log_timeformat_fractional_seconds(frozen_time, logged_time, tmpdir):
    with freeze_time(frozen_time):

        class App:
            config = {
                "NOTIFY_APP_NAME": "bar",
                "NOTIFY_LOG_LEVEL": "INFO",
            }
            debug = False

        app = App()

        handlers = logging.get_handlers(app, extra_filters=[])

        record = builtin_logging.LogRecord(
            name="log thing", level="info", pathname="path", lineno=123, msg="message to log", exc_info=None, args=None
        )
        record.service_id = 1234
        assert json.loads(handlers[0].format(record))["time"] == logged_time


def test_base_json_formatter_contains_service_id(tmpdir):
    record = builtin_logging.LogRecord(
        name="log thing", level="info", pathname="path", lineno=123, msg="message to log", exc_info=None, args=None
    )

    service_id_filter = logging.ServiceIdFilter()
    assert json.loads(logging.BaseJSONFormatter().format(record))["message"] == "message to log"
    assert service_id_filter.filter(record).service_id == "no-service-id"


@pytest.mark.parametrize(
    "status_code,expected_after_level,with_request_helper",
    (
        (200, builtin_logging.INFO, False),
        (200, builtin_logging.INFO, True),
        (200, builtin_logging.INFO, False),
        (201, builtin_logging.INFO, False),
        (400, builtin_logging.INFO, False),
        (503, builtin_logging.WARNING, False),
        (503, builtin_logging.WARNING, True),
    ),
)
def test_app_request_logs_level_by_status_code(
    app_with_mocked_logger,
    status_code,
    expected_after_level,
    with_request_helper,
):
    app = app_with_mocked_logger
    app.config["NOTIFY_ENVIRONMENT"] = "foo"
    mock_req_logger = mock.Mock(
        spec=builtin_logging.Logger("flask.app.request"),
        handlers=[],
    )
    app.logger.getChild.side_effect = lambda name: mock_req_logger if name == "request" else mock.DEFAULT

    if with_request_helper:
        request_helper.init_app(app)
    logging.init_app(app)

    @app.route("/")
    def some_route():
        time.sleep(0.05)
        return "foo", status_code

    app.test_client().get("/", headers={"x-b3-parentspanid": "deadbeef"})

    assert (
        mock.call(
            builtin_logging.DEBUG,
            "Received request %(method)s %(url)s",
            {
                "url": "http://localhost/",
                "method": "GET",
                "endpoint": "some_route",
                "host": "localhost",
                "path": "/",
                "environment": "foo",
                "request_size": 0,
                "user_agent": AnyStringMatching("Werkzeug.*"),
                "remote_addr": "127.0.0.1",
                "parent_span_id": "deadbeef" if with_request_helper else None,
                "process_": RestrictedAny(lambda value: isinstance(value, int)),
            },
            extra={
                "url": "http://localhost/",
                "method": "GET",
                "endpoint": "some_route",
                "host": "localhost",
                "environment": "foo",
                "request_size": 0,
                "path": "/",
                "user_agent": AnyStringMatching("Werkzeug.*"),
                "remote_addr": "127.0.0.1",
                "parent_span_id": "deadbeef" if with_request_helper else None,
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
                "host": "localhost",
                "path": "/",
                "user_agent": AnyStringMatching("Werkzeug.*"),
                "method": "GET",
                "environment": "foo",
                "request_size": 0,
                "response_size": 3,
                "endpoint": "some_route",
                "remote_addr": "127.0.0.1",
                "parent_span_id": "deadbeef" if with_request_helper else None,
                "status": status_code,
                "request_time": RestrictedAny(lambda value: isinstance(value, float) and 0.05 <= value),
                "process_": RestrictedAny(lambda value: isinstance(value, int)),
            },
            extra={
                "url": "http://localhost/",
                "host": "localhost",
                "path": "/",
                "user_agent": AnyStringMatching("Werkzeug.*"),
                "method": "GET",
                "environment": "foo",
                "request_size": 0,
                "response_size": 3,
                "endpoint": "some_route",
                "remote_addr": "127.0.0.1",
                "parent_span_id": "deadbeef" if with_request_helper else None,
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
                "host": "localhost",
                "environment": "",
                "request_size": 0,
                "path": "/",
                "user_agent": AnyStringMatching("Werkzeug.*"),
                "remote_addr": "127.0.0.1",
                "parent_span_id": None,
                "process_": RestrictedAny(lambda value: isinstance(value, int)),
            },
            extra={
                "url": "http://localhost/",
                "method": "GET",
                "endpoint": "some_route",
                "host": "localhost",
                "environment": "",
                "request_size": 0,
                "path": "/",
                "user_agent": AnyStringMatching("Werkzeug.*"),
                "remote_addr": "127.0.0.1",
                "parent_span_id": None,
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
                "environment": "",
                "request_size": 0,
                "response_size": RestrictedAny(lambda x: x > 10),
                "host": "localhost",
                "path": "/",
                "user_agent": AnyStringMatching("Werkzeug.*"),
                "remote_addr": "127.0.0.1",
                "parent_span_id": None,
                "status": 500,
                "request_time": RestrictedAny(lambda value: isinstance(value, float) and 0.05 <= value),
                "process_": RestrictedAny(lambda value: isinstance(value, int)),
            },
            extra={
                "url": "http://localhost/",
                "method": "GET",
                "endpoint": "some_route",
                "environment": "",
                "request_size": 0,
                "response_size": RestrictedAny(lambda x: x > 10),
                "host": "localhost",
                "path": "/",
                "user_agent": AnyStringMatching("Werkzeug.*"),
                "remote_addr": "127.0.0.1",
                "parent_span_id": None,
                "status": 500,
                "request_time": RestrictedAny(lambda value: isinstance(value, float) and 0.05 <= value),
                "process_": RestrictedAny(lambda value: isinstance(value, int)),
            },
        )
        in mock_req_logger.log.call_args_list
    )


def test_app_request_logs_response_on_status_200(app_with_mocked_logger):
    app = app_with_mocked_logger
    app.config["NOTIFY_ENVIRONMENT"] = "bar"
    mock_req_logger = mock.Mock(
        spec=builtin_logging.Logger("flask.app.request"),
        handlers=[],
    )
    status_fail = False

    @app.route("/_status")
    def status():
        if status_fail:
            return "FAIL", 500
        return "OK", 200

    @app.route("/metrics")
    def metrics():
        return "OK", 200

    app.logger.getChild.side_effect = lambda name: mock_req_logger if name == "request" else mock.DEFAULT

    logging.init_app(app)

    app.test_client().get("/_status")

    assert (
        mock.call(
            builtin_logging.DEBUG,
            "%(method)s %(url)s %(status)s took %(request_time)ss",
            {
                "url": "http://localhost/_status",
                "method": "GET",
                "endpoint": "status",
                "environment": "bar",
                "request_size": 0,
                "response_size": 2,
                "host": "localhost",
                "path": "/_status",
                "user_agent": AnyStringMatching("Werkzeug.*"),
                "remote_addr": "127.0.0.1",
                "parent_span_id": None,
                "status": 200,
                "request_time": RestrictedAny(lambda value: isinstance(value, float)),
                "process_": RestrictedAny(lambda value: isinstance(value, int)),
            },
            extra={
                "url": "http://localhost/_status",
                "method": "GET",
                "endpoint": "status",
                "environment": "bar",
                "request_size": 0,
                "response_size": 2,
                "host": "localhost",
                "path": "/_status",
                "user_agent": AnyStringMatching("Werkzeug.*"),
                "remote_addr": "127.0.0.1",
                "parent_span_id": None,
                "status": 200,
                "request_time": RestrictedAny(lambda value: isinstance(value, float)),
                "process_": RestrictedAny(lambda value: isinstance(value, int)),
            },
        )
        in mock_req_logger.log.call_args_list
    )

    app.test_client().get("/metrics")

    assert (
        mock.call(
            builtin_logging.DEBUG,
            "%(method)s %(url)s %(status)s took %(request_time)ss",
            {
                "url": "http://localhost/metrics",
                "method": "GET",
                "endpoint": "metrics",
                "environment": "bar",
                "request_size": 0,
                "response_size": 2,
                "host": "localhost",
                "path": "/metrics",
                "user_agent": AnyStringMatching("Werkzeug.*"),
                "remote_addr": "127.0.0.1",
                "parent_span_id": None,
                "status": 200,
                "request_time": RestrictedAny(lambda value: isinstance(value, float)),
                "process_": RestrictedAny(lambda value: isinstance(value, int)),
            },
            extra={
                "url": "http://localhost/metrics",
                "method": "GET",
                "endpoint": "metrics",
                "environment": "bar",
                "request_size": 0,
                "response_size": 2,
                "host": "localhost",
                "path": "/metrics",
                "user_agent": AnyStringMatching("Werkzeug.*"),
                "remote_addr": "127.0.0.1",
                "parent_span_id": None,
                "status": 200,
                "request_time": RestrictedAny(lambda value: isinstance(value, float)),
                "process_": RestrictedAny(lambda value: isinstance(value, int)),
            },
        )
        in mock_req_logger.log.call_args_list
    )

    status_fail = True
    app.test_client().get("/_status")

    assert (
        mock.call(
            builtin_logging.WARNING,
            "%(method)s %(url)s %(status)s took %(request_time)ss",
            {
                "url": "http://localhost/_status",
                "method": "GET",
                "endpoint": "status",
                "environment": "bar",
                "request_size": 0,
                "response_size": 4,
                "host": "localhost",
                "path": "/_status",
                "user_agent": AnyStringMatching("Werkzeug.*"),
                "remote_addr": "127.0.0.1",
                "parent_span_id": None,
                "status": 500,
                "request_time": RestrictedAny(lambda value: isinstance(value, float)),
                "process_": RestrictedAny(lambda value: isinstance(value, int)),
            },
            extra={
                "url": "http://localhost/_status",
                "method": "GET",
                "endpoint": "status",
                "environment": "bar",
                "request_size": 0,
                "response_size": 4,
                "host": "localhost",
                "path": "/_status",
                "user_agent": AnyStringMatching("Werkzeug.*"),
                "remote_addr": "127.0.0.1",
                "parent_span_id": None,
                "status": 500,
                "request_time": RestrictedAny(lambda value: isinstance(value, float)),
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
                "environment": "",
                "request_size": 0,
                "host": "localhost",
                "path": "/foo",
                "user_agent": AnyStringMatching("Werkzeug.*"),
                "remote_addr": "127.0.0.1",
                "parent_span_id": None,
                "process_": RestrictedAny(lambda value: isinstance(value, int)),
            },
            extra={
                "url": "http://localhost/foo",
                "method": "GET",
                "endpoint": None,
                "environment": "",
                "request_size": 0,
                "host": "localhost",
                "path": "/foo",
                "user_agent": AnyStringMatching("Werkzeug.*"),
                "remote_addr": "127.0.0.1",
                "parent_span_id": None,
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
                "environment": "",
                "request_size": 0,
                "response_size": RestrictedAny(lambda x: x > 0),
                "host": "localhost",
                "path": "/foo",
                "user_agent": AnyStringMatching("Werkzeug.*"),
                "remote_addr": "127.0.0.1",
                "parent_span_id": None,
                "status": 404,
                "request_time": RestrictedAny(lambda value: isinstance(value, float)),
                "process_": RestrictedAny(lambda value: isinstance(value, int)),
            },
            extra={
                "url": "http://localhost/foo",
                "method": "GET",
                "endpoint": None,
                "environment": "",
                "request_size": 0,
                "response_size": RestrictedAny(lambda x: x > 0),
                "host": "localhost",
                "path": "/foo",
                "user_agent": AnyStringMatching("Werkzeug.*"),
                "remote_addr": "127.0.0.1",
                "parent_span_id": None,
                "status": 404,
                "request_time": RestrictedAny(lambda value: isinstance(value, float)),
                "process_": RestrictedAny(lambda value: isinstance(value, int)),
            },
        )
        in mock_req_logger.log.call_args_list
    )


def test_app_request_logs_responses_on_post(app_with_mocked_logger):
    app = app_with_mocked_logger
    mock_req_logger = mock.Mock(
        spec=builtin_logging.Logger("flask.app.request"),
        handlers=[],
    )
    app.logger.getChild.side_effect = lambda name: mock_req_logger if name == "request" else mock.DEFAULT

    @app.route("/post", methods=["POST"])
    def post():
        return "OK", 200

    logging.init_app(app)

    app.test_client().post("/post", data="foo=bar")

    assert (
        mock.call(
            builtin_logging.DEBUG,
            "Received request %(method)s %(url)s",
            {
                "url": "http://localhost/post",
                "method": "POST",
                "endpoint": "post",
                "environment": "",
                "request_size": 7,
                "host": "localhost",
                "path": "/post",
                "user_agent": AnyStringMatching("Werkzeug.*"),
                "remote_addr": "127.0.0.1",
                "parent_span_id": None,
                "process_": RestrictedAny(lambda value: isinstance(value, int)),
            },
            extra={
                "url": "http://localhost/post",
                "method": "POST",
                "endpoint": "post",
                "environment": "",
                "request_size": 7,
                "host": "localhost",
                "path": "/post",
                "user_agent": AnyStringMatching("Werkzeug.*"),
                "remote_addr": "127.0.0.1",
                "parent_span_id": None,
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
                "url": "http://localhost/post",
                "method": "POST",
                "endpoint": "post",
                "environment": "",
                "request_size": 7,
                "response_size": 2,
                "host": "localhost",
                "path": "/post",
                "user_agent": AnyStringMatching("Werkzeug.*"),
                "remote_addr": "127.0.0.1",
                "parent_span_id": None,
                "status": 200,
                "request_time": RestrictedAny(lambda value: isinstance(value, float)),
                "process_": RestrictedAny(lambda value: isinstance(value, int)),
            },
            extra={
                "url": "http://localhost/post",
                "method": "POST",
                "endpoint": "post",
                "environment": "",
                "request_size": 7,
                "response_size": 2,
                "host": "localhost",
                "path": "/post",
                "user_agent": AnyStringMatching("Werkzeug.*"),
                "remote_addr": "127.0.0.1",
                "parent_span_id": None,
                "status": 200,
                "request_time": RestrictedAny(lambda value: isinstance(value, float)),
                "process_": RestrictedAny(lambda value: isinstance(value, int)),
            },
        )
        in mock_req_logger.log.call_args_list
    )


def test_app_request_logs_responses_over_max_content(app_with_mocked_logger):
    app = app_with_mocked_logger

    app.config["MAX_CONTENT_LENGTH"] = 3 * 1024 * 1024
    mock_req_logger = mock.Mock(
        spec=builtin_logging.Logger("flask.app.request"),
        handlers=[],
    )
    app.logger.getChild.side_effect = lambda name: mock_req_logger if name == "request" else mock.DEFAULT

    @app.route("/post", methods=["POST"])
    def post():
        from flask import request

        # need to access data to trigger data too large error
        _ = request.data
        return "OK", 200

    logging.init_app(app)

    file_content = b"a" * (3 * 1024 * 1024 + 1)
    response = app.test_client().post("/post", data=file_content)
    assert response.status_code == 413

    assert (
        mock.call(
            builtin_logging.DEBUG,
            "Received request %(method)s %(url)s",
            {
                "url": "http://localhost/post",
                "method": "POST",
                "endpoint": "post",
                "environment": "",
                "request_size": (3 * 1024 * 1024 + 1),
                "host": "localhost",
                "path": "/post",
                "user_agent": AnyStringMatching("Werkzeug.*"),
                "remote_addr": "127.0.0.1",
                "parent_span_id": None,
                "process_": RestrictedAny(lambda value: isinstance(value, int)),
            },
            extra={
                "url": "http://localhost/post",
                "method": "POST",
                "endpoint": "post",
                "environment": "",
                "request_size": 3145729,
                "host": "localhost",
                "path": "/post",
                "user_agent": AnyStringMatching("Werkzeug.*"),
                "remote_addr": "127.0.0.1",
                "parent_span_id": None,
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
                "url": "http://localhost/post",
                "method": "POST",
                "endpoint": "post",
                "environment": "",
                "request_size": (3 * 1024 * 1024 + 1),
                "response_size": RestrictedAny(lambda x: x > 0),
                "host": "localhost",
                "path": "/post",
                "user_agent": AnyStringMatching("Werkzeug.*"),
                "remote_addr": "127.0.0.1",
                "parent_span_id": None,
                "status": 413,
                "request_time": RestrictedAny(lambda value: isinstance(value, float)),
                "process_": RestrictedAny(lambda value: isinstance(value, int)),
            },
            extra={
                "url": "http://localhost/post",
                "method": "POST",
                "endpoint": "post",
                "environment": "",
                "request_size": 3145729,
                "response_size": RestrictedAny(lambda x: x > 0),
                "host": "localhost",
                "path": "/post",
                "user_agent": AnyStringMatching("Werkzeug.*"),
                "remote_addr": "127.0.0.1",
                "parent_span_id": None,
                "status": 413,
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
