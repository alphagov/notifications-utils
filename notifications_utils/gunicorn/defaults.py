# this will be imported at a very early stage of gunicorn initialization, so must
# be very restrained with imports

import os
import sys
import traceback

import gunicorn
from gunicorn.glogging import CONFIG_DEFAULTS as LOGGING_CONFIG_DEFAULTS


def on_starting(server):
    notify_app_name = os.getenv("NOTIFY_APP_NAME")
    server.log.info("Starting webapp %s", notify_app_name, extra={"notify_app_name": notify_app_name})


def on_exit(server):
    notify_app_name = os.getenv("NOTIFY_APP_NAME")
    server.log.info("Stopping webapp %s", notify_app_name, extra={"notify_app_name": notify_app_name})


def post_fork(server, worker):
    import logging

    # near-silence messages generated before app has set its own logging up
    for handler in logging.getLogger().handlers:
        handler.setLevel(logging.ERROR)


def worker_int(worker):
    worker.log.info("worker pid %s received SIGINT", worker.pid, extra={"process_": worker.pid})


def worker_abort(worker):
    worker.log.info("worker pid %s received ABORT", worker.pid, extra={"process_": worker.pid})
    for _threadId, stack in sys._current_frames().items():
        worker.log.error("".join(traceback.format_stack(stack)))


# a globals-mutating function because we need to update values in other modules, which
# isn't very nice to do at import-time
def set_gunicorn_defaults(globals_dict: dict):
    globals_dict.update(
        bind=f"0.0.0.0:{os.getenv('PORT', '8080')}",
        disable_redirect_access_to_syslog=True,
        logconfig_dict={
            **LOGGING_CONFIG_DEFAULTS,
            "loggers": {
                **LOGGING_CONFIG_DEFAULTS.get("loggers", {}),
                "gunicorn.error": {
                    **LOGGING_CONFIG_DEFAULTS.get("loggers", {}).get("gunicorn.error", {}),
                    "propagate": False,  # avoid duplicates
                },
                "gunicorn.access": {
                    **LOGGING_CONFIG_DEFAULTS.get("loggers", {}).get("gunicorn.access", {}),
                    "level": "CRITICAL",
                    "propagate": False,
                },
            },
            "formatters": {
                **LOGGING_CONFIG_DEFAULTS.get("formatters", {}),
                "generic": {
                    "class": "notifications_utils.logging.formatting.JSONFormatter",
                    "format": "ext://notifications_utils.logging.formatting.LOG_FORMAT",
                    "datefmt": "ext://notifications_utils.logging.formatting.TIME_FORMAT",
                },
            },
        },
        on_exit=on_exit,
        on_starting=on_starting,
        post_fork=post_fork,
        worker_abort=worker_abort,
        worker_int=worker_int,
    )
    gunicorn.SERVER_SOFTWARE = "None"
