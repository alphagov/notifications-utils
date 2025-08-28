from logging.config import dictConfig

from celery.signals import setup_logging

config = None


def set_up_logging(conf):
    global config
    config = conf
    # we connect to the setup_logging signal to configure logging during the worker startup
    # and beat startup. If we don't do this and go directly to the setup_logging_connect
    # we will not have some of the startup messages.
    setup_logging.connect(setup_logging_connect)


def setup_logging_connect(*args, **kwargs):
    if config is None:
        raise ValueError("Configuration object is not set. Please call set_up_logging first.")

    worker_log_level = config.get("CELERY_WORKER_LOG_LEVEL", "CRITICAL").upper()
    beat_log_level = config.get("CELERY_BEAT_LOG_LEVEL", "INFO").upper()

    # Override the default celery logger to use the JSON formatter
    # We need to be very careful with the worker logger as it can leak PII data
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
                "formatter": "generic",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",  # Default is stderr
            },
        },
        "loggers": {
            "celery.worker": {"handlers": ["default"], "level": worker_log_level, "propagate": False},
            "celery.beat": {"handlers": ["default"], "level": beat_log_level, "propagate": False},
        },
    }

    dictConfig(LOGGING_CONFIG)
