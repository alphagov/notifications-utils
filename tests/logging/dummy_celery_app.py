import logging
import os
import signal

from celery import Celery
from pythonjsonlogger.json import JsonFormatter

import notifications_utils.logging.celery as celery_logging

logger = logging.getLogger()

logHandler = logging.StreamHandler()
formatter = JsonFormatter()
logHandler.setFormatter(formatter)
logger.addHandler(logHandler)

celery_logging.set_up_logging(logger)


app = Celery("test_app")
app.conf.update(
    broker_url="memory://",  # deliberate celery failure
)

WORKER_PID = os.getpid()


@app.task
def test_task():
    os.kill(WORKER_PID, signal.SIGTERM)


test_task.delay()
