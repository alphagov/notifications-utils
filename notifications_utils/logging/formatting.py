# This file is intentionally minimal to make it importable from gunicorn_config.py
import logging

from pythonjsonlogger.jsonlogger import JsonFormatter as BaseJSONFormatter

LOG_FORMAT = '%(asctime)s %(app_name)s %(name)s %(levelname)s %(request_id)s "%(message)s" [in %(pathname)s:%(lineno)d]'
TIME_FORMAT = "%Y-%m-%dT%H:%M:%S"


class _MicrosecondAddingFormatterMixin:
    """
    Appends a `.` and then a 6-digit number of microseconds to whatever
    the superclass' `.formatTime(...)` returns.
    """

    # This is necessary because  supplying a `datefmt` causes the base
    # `formatTime` implementation to completely bypass any code that
    # would be able to add milliseconds (let alone microseconds" to the
    # formatted time.

    def formatTime(self, record, *args, **kwargs):
        formatted = super().formatTime(record, *args, **kwargs)
        return f"{formatted}.{int((record.created - int(record.created)) * 1e6):06}"


class Formatter(_MicrosecondAddingFormatterMixin, logging.Formatter):
    pass


class JSONFormatter(_MicrosecondAddingFormatterMixin, BaseJSONFormatter):
    def process_log_record(self, log_record):
        rename_map = {
            "asctime": "time",
            "request_id": "requestId",
            "app_name": "application",
            "service_id": "service_id",
        }
        for key, newkey in rename_map.items():
            log_record[newkey] = log_record.pop(key, None)
        log_record["logType"] = "application"
        return log_record
