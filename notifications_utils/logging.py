import logging
import logging.handlers
import sys
from itertools import product
from pathlib import Path
from typing import Sequence

from flask import g, request
from flask.ctx import has_app_context, has_request_context
from pythonjsonlogger.jsonlogger import JsonFormatter as BaseJSONFormatter

LOG_FORMAT = (
    "%(asctime)s %(app_name)s %(name)s %(levelname)s " '%(request_id)s "%(message)s" [in %(pathname)s:%(lineno)d]'
)
TIME_FORMAT = "%Y-%m-%dT%H:%M:%S"

logger = logging.getLogger(__name__)


def init_app(app, statsd_client=None, extra_filters: Sequence[logging.Filter] = tuple()):
    app.config.setdefault("NOTIFY_LOG_LEVEL", "INFO")
    app.config.setdefault("NOTIFY_APP_NAME", "none")
    app.config.setdefault("NOTIFY_LOG_PATH", "./log/application.log")
    app.config.setdefault("NOTIFY_RUNTIME_PLATFORM", None)

    logging.getLogger().addHandler(logging.NullHandler())

    del app.logger.handlers[:]

    if app.config["NOTIFY_RUNTIME_PLATFORM"] != "ecs":
        # TODO: ecs-migration: check if we still need this function after we migrate to ecs
        ensure_log_path_exists(app.config["NOTIFY_LOG_PATH"])

    handlers = get_handlers(app, extra_filters=extra_filters)
    loglevel = logging.getLevelName(app.config["NOTIFY_LOG_LEVEL"])
    loggers = [app.logger, logging.getLogger("utils")]
    for logger_instance, handler in product(loggers, handlers):
        logger_instance.addHandler(handler)
        logger_instance.setLevel(loglevel)
    logging.getLogger("boto3").setLevel(logging.WARNING)
    logging.getLogger("s3transfer").setLevel(logging.WARNING)
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
    standard_formatter = logging.Formatter(LOG_FORMAT, TIME_FORMAT)
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

    # TODO: ecs-migration: delete this when we migrate to ecs
    # only write json to file if we're not running on ECS
    if app.config["NOTIFY_RUNTIME_PLATFORM"] != "ecs":
        # machine readable json to both file and stdout
        file_handler = logging.handlers.WatchedFileHandler(filename=f"{app.config['NOTIFY_LOG_PATH']}.json")
        handlers.append(configure_handler(file_handler, app, json_formatter, extra_filters=extra_filters))

    return handlers


def configure_handler(handler, app, formatter, *, extra_filters: Sequence[logging.Filter]):
    handler.setLevel(logging.getLevelName(app.config["NOTIFY_LOG_LEVEL"]))
    handler.setFormatter(formatter)
    handler.addFilter(AppNameFilter(app.config["NOTIFY_APP_NAME"]))
    handler.addFilter(RequestIdFilter())
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
            return "no-request-id"

    def filter(self, record):
        record.request_id = self.request_id

        return record


class ServiceIdFilter(logging.Filter):
    @property
    def service_id(self):
        if has_app_context() and "service_id" in g:
            return g.service_id
        else:
            return "no-service-id"

    def filter(self, record):
        record.service_id = self.service_id

        return record


class UserIdFilter(logging.Filter):
    @property
    def user_id(self):
        if has_app_context() and "user_id" in g:
            return g.user_id
        else:
            return None

    def filter(self, record):
        record.user_id = self.user_id
        return record


class JSONFormatter(BaseJSONFormatter):
    def process_log_record(self, log_record):
        rename_map = {
            "asctime": "time",
            "request_id": "requestId",
            "app_name": "application",
            "service_id": "service_id",
        }
        for key, newkey in rename_map.items():
            log_record[newkey] = log_record.pop(key)
        log_record["logType"] = "application"
        return log_record
