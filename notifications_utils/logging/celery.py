import os
import warnings
from logging.config import dictConfig

from celery.signals import setup_logging


def set_up_logging(logger):
    if logger is None or not hasattr(logger, "warning"):
        raise AttributeError("The provided logger object is invalid.")

    def custom_showwarning(message, category, filename, lineno, file=None, line=None):
        log_entry = {
            "level": "WARNING",
            "message": str(message),
            "category": category.__name__,
            "filename": filename,
            "lineno": lineno,
        }
        logger.warning(str(message), log_entry)

    warnings.showwarning = custom_showwarning

    setup_logging.connect(setup_logging_connect)


def setup_logging_connect(*args, **kwargs):
    log_level = os.environ.get("CELERY_LOG_LEVEL", "CRITICAL").upper()

    LOGGING_CONFIG = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "generic": {
                "class": "notifications_utils.logging.formatting.JSONFormatter",
                "format": "ext://notifications_utils.logging.formatting.LOG_FORMAT",
                "datefmt": "ext://notifications_utils.logging.formatting.TIME_FORMAT",
            },
        },
        "handlers": {
            "default": {
                "level": log_level,
                "formatter": "generic",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",  # Default is stderr
            },
        },
        "loggers": {
            "celery.worker": {"handlers": ["default"], "level": log_level, "propagate": True},
        },
    }

    dictConfig(LOGGING_CONFIG)
