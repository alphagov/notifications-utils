import logging
import logging.handlers
import sys
from collections.abc import Sequence
from functools import partial
from itertools import product
from os import getpid
from pathlib import Path
from time import perf_counter_ns

from flask import current_app, g, request
from flask.ctx import has_app_context, has_request_context

import notifications_utils.eventlet as utils_eventlet

if utils_eventlet.using_eventlet:
    thread_time_ns = utils_eventlet.greenlet_thread_time_ns
else:
    from time import thread_time_ns

from .formatting import (
    LOG_FORMAT,
    TIME_FORMAT,
    BaseJSONFormatter,  # noqa
    Formatter,
    JSONFormatter,
)

logger = logging.getLogger(__name__)

_ns_per_s = 1.0e-9


def _common_request_extra_log_context():
    return {
        "method": request.method,
        "url": request.url,
        "environment": current_app.config["NOTIFY_ENVIRONMENT"] if "NOTIFY_ENVIRONMENT" in current_app.config else "",
        "request_size": request.content_length if request.content_length is not None else 0,
        "endpoint": request.endpoint,
        "remote_addr": request.remote_addr,
        "user_agent": request.user_agent.string,
        "host": request.host.split(":", 1)[0],
        "path": request.path,
        "parent_span_id": getattr(request, "parent_span_id", None),
        # pid and is available on LogRecord by default, as `process` but I don't see
        # a straightforward way of selectively including it only in certain log messages -
        # it is designed to be included when the formatter is being configured. This is
        # why I'm manually grabbing it and putting it in as `extra` here, avoiding the
        # existing parameter name to prevent LogRecord from complaining
        "process_": getpid(),
    }


def _eventlet_stats_extra_log_context(request_time: float | None) -> dict:
    greenlet_context_switch_count = utils_eventlet.greenlet_context_switch_count()
    before_request_greenlet_context_switch_count = getattr(
        request, "before_request_greenlet_context_switch_count", None
    )

    context = {
        "greenlet_context_switches": (
            None
            if greenlet_context_switch_count is None or before_request_greenlet_context_switch_count is None
            else greenlet_context_switch_count - before_request_greenlet_context_switch_count
        ),
        "greenlet_real_time_max_continuous": utils_eventlet.greenlet_perf_counter_ns_max_continuous() * _ns_per_s,
        "greenlet_cpu_time_max_continuous": utils_eventlet.greenlet_thread_time_ns_max_continuous() * _ns_per_s,
    }
    if request_time and request_time > current_app.config["NOTIFY_EVENTLET_STATS_VERBOSE_THRESHOLD_SECONDS"]:
        context.update(utils_eventlet.get_main_greenlets_debug_info())

    return context


def _log_response_closed(
    logger,
    log_level,
    response,
    before_request_perf_counter_ns,
    before_request_thread_time_ns,
    common_request_extra_log_context,
):
    _perf_counter_ns = perf_counter_ns()
    _thread_time_ns = thread_time_ns()
    context = {
        "status": response.status_code,
        "request_time": (
            (_perf_counter_ns - before_request_perf_counter_ns) * _ns_per_s
            if before_request_perf_counter_ns is not None
            else None
        ),
        "request_cpu_time": (
            (_thread_time_ns - before_request_thread_time_ns) * _ns_per_s
            if before_request_thread_time_ns is not None and _thread_time_ns is not None
            else None
        ),
        # response size not reliably available at this point :(
        "response_streamed": True,
        **common_request_extra_log_context,
    }
    logger.getChild("request").log(
        log_level,
        "Streaming response for %(method)s %(url)s %(status)s closed after %(request_time)ss",
        context,
        extra=context,
    )


def init_app(app, statsd_client=None, extra_filters: Sequence[logging.Filter] = ()):
    app.config.setdefault("NOTIFY_LOG_LEVEL", "INFO")
    app.config.setdefault("NOTIFY_LOG_LEVEL_HANDLERS", app.config["NOTIFY_LOG_LEVEL"])
    app.config.setdefault("NOTIFY_APP_NAME", "none")
    app.config.setdefault("NOTIFY_LOG_DEBUG_PATH_LIST", {"/_status", "/metrics"})
    app.config.setdefault("NOTIFY_REQUEST_LOG_LEVEL", "CRITICAL")
    app.config.setdefault("NOTIFY_EVENTLET_STATS", False)
    app.config.setdefault("NOTIFY_EVENTLET_STATS_VERBOSE_THRESHOLD_SECONDS", 1.0)

    @app.before_request
    def before_request():
        # annotating this onto request instead of flask.g as it probably shouldn't
        # be inheritable from a request-less application context
        request.before_request_perf_counter_ns = perf_counter_ns()
        request.before_request_thread_time_ns = thread_time_ns()

        if app.config["NOTIFY_EVENTLET_STATS"]:
            request.before_request_greenlet_context_switch_count = utils_eventlet.greenlet_context_switch_count()
            utils_eventlet.reset_greenlet_stats()

        # emit an early log message to record that the request was received by the app
        context = _common_request_extra_log_context()
        current_app.logger.getChild("request").log(
            logging.DEBUG,
            "Received request %(method)s %(url)s",
            context,
            extra=context,
        )

    @app.after_request
    def after_request(response):
        log_level = logging.INFO

        # Failures are logged at a higher level
        if response.status_code // 100 == 5:
            log_level = logging.WARNING

        # We do not want to log the NOTIFY_LOG_DEBUG_PATH_LIST set at INFO level.
        # For example status checks and metrics endpoints.
        if request.path in app.config["NOTIFY_LOG_DEBUG_PATH_LIST"] and not (500 <= response.status_code < 600):
            log_level = logging.DEBUG

        _perf_counter_ns = perf_counter_ns()
        _thread_time_ns = thread_time_ns()
        context = {
            "status": response.status_code,
            "request_time": (
                (_perf_counter_ns - request.before_request_perf_counter_ns) * _ns_per_s
                if getattr(request, "before_request_perf_counter_ns", None) is not None
                else None
            ),
            "request_cpu_time": (
                (_thread_time_ns - request.before_request_thread_time_ns) * _ns_per_s
                if getattr(request, "before_request_thread_time_ns", None) is not None
                else None
            ),
            "response_size": None if response.is_streamed else response.calculate_content_length(),
            "response_streamed": response.is_streamed,
            **_common_request_extra_log_context(),
        }
        if app.config["NOTIFY_EVENTLET_STATS"]:
            context.update(_eventlet_stats_extra_log_context(context["request_time"]))

        current_app.logger.getChild("request").log(
            log_level,
            "%(method)s %(url)s %(status)s took %(request_time)ss",
            context,
            extra=context,
        )

        if response.is_streamed:
            response.call_on_close(
                partial(
                    _log_response_closed,
                    current_app.logger,
                    log_level,
                    response,
                    getattr(request, "before_request_perf_counter_ns", None),
                    getattr(request, "before_request_thread_time_ns", None),
                    # this is horrible, but call_on_close hook can't use `request` itself, meaning these filters
                    # and _common_request_extra_log_context() won't work normally when that is called, meaning
                    # we need to "pre-bake" their values now.
                    {
                        "request_id": RequestIdFilter().request_id,
                        "service_id": ServiceIdFilter().service_id,
                        "span_id": SpanIdFilter().span_id,
                        "user_id": UserIdFilter().user_id,
                        **_common_request_extra_log_context(),
                    },
                )
            )

        return response

    app.logger.handlers.clear()
    logging.getLogger().handlers.clear()
    # avoid lastResort handler coming into play
    logging.getLogger().addHandler(logging.NullHandler())

    handlers = get_handlers(app, extra_filters=extra_filters)
    loglevel = logging.getLevelName(app.config["NOTIFY_LOG_LEVEL"])
    loggers = [
        app.logger,
        logging.getLogger("utils"),
    ]
    for logger_instance, handler in product(loggers, handlers):
        logger_instance.addHandler(handler)
        logger_instance.setLevel(loglevel)
    logging.getLogger("boto3").setLevel(logging.WARNING)
    logging.getLogger("s3transfer").setLevel(logging.WARNING)

    request_loglevel = logging.getLevelName(app.config["NOTIFY_REQUEST_LOG_LEVEL"])
    app.logger.getChild("request").setLevel(request_loglevel)

    app.logger.info("Logging configured")


def ensure_log_path_exists(path):
    """
    This function assumes you're passing a path to a file and attempts to create
    the path leading to that file.
    """
    try:
        Path(path).parent.mkdir(mode=755, parents=True)
    except FileExistsError:
        pass


def get_handlers(app, extra_filters: Sequence[logging.Filter]):
    handlers = []
    standard_formatter = Formatter(LOG_FORMAT, TIME_FORMAT)
    json_formatter = JSONFormatter(LOG_FORMAT, TIME_FORMAT)

    stream_handler = logging.StreamHandler(sys.stdout)

    if app.debug:
        # turn off 200 OK static logs in development
        def is_200_static_log(log):
            msg = log.getMessage()
            return not ("GET /static/" in msg and " 200 " in msg)

        logging.getLogger("werkzeug").addFilter(is_200_static_log)

        # human readable stdout logs
        handlers.append(configure_handler(stream_handler, app, standard_formatter, extra_filters=extra_filters))
        return handlers

    # stream json to stdout in all cases
    handlers.append(configure_handler(stream_handler, app, json_formatter, extra_filters=extra_filters))

    return handlers


def configure_handler(handler, app, formatter, *, extra_filters: Sequence[logging.Filter]):
    handler.setLevel(logging.getLevelName(app.config["NOTIFY_LOG_LEVEL_HANDLERS"]))
    handler.setFormatter(formatter)
    handler.addFilter(AppNameFilter(app.config["NOTIFY_APP_NAME"]))
    handler.addFilter(RequestIdFilter())
    handler.addFilter(SpanIdFilter())
    handler.addFilter(ServiceIdFilter())
    handler.addFilter(UserIdFilter())

    for extra_filter in extra_filters:
        handler.addFilter(extra_filter)

    return handler


class AppNameFilter(logging.Filter):
    def __init__(self, app_name):
        self.app_name = app_name

    def filter(self, record):
        record.app_name = self.app_name

        return record


class RequestIdFilter(logging.Filter):
    @property
    def request_id(self):
        if has_request_context() and hasattr(request, "request_id"):
            return request.request_id
        elif has_app_context() and "request_id" in g:
            return g.request_id
        else:
            return None

    def filter(self, record):
        record.request_id = self.request_id or getattr(record, "request_id", None) or "no-request-id"

        return record


class SpanIdFilter(logging.Filter):
    @property
    def span_id(self):
        if has_request_context() and hasattr(request, "span_id"):
            return request.span_id
        elif has_app_context() and "span_id" in g:
            return g.span_id
        else:
            return None

    def filter(self, record):
        record.span_id = self.span_id or getattr(record, "span_id", None) or "no-span-id"

        return record


class ServiceIdFilter(logging.Filter):
    @property
    def service_id(self):
        if has_app_context() and "service_id" in g:
            return g.service_id
        else:
            return None

    def filter(self, record):
        record.service_id = self.service_id or getattr(record, "service_id", None) or "no-service-id"

        return record


class UserIdFilter(logging.Filter):
    @property
    def user_id(self):
        if has_app_context() and "user_id" in g:
            return g.user_id
        else:
            return None

    def filter(self, record):
        record.user_id = self.user_id or getattr(record, "user_id", None)
        return record
