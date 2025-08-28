import os
import signal
import tempfile
from datetime import timedelta

from celery import Celery

import notifications_utils.logging.celery as celery_logging


class Config:
    CELERY_WORKER_LOG_LEVEL = os.getenv("CELERY_WORKER_LOG_LEVEL", "CRITICAL").upper()
    CELERY_BEAT_LOG_LEVEL = os.getenv("CELERY_BEAT_LOG_LEVEL", "INFO").upper()

    def get(self, key, default=None):
        return getattr(self, key, default)


celery_logging.set_up_logging(Config())

temp_dir = tempfile.mkdtemp()
app = Celery("test_app")
app.conf.update(
    broker_url="filesystem://",
    broker_transport_options={
        "data_folder_in": temp_dir,
        "data_folder_out": temp_dir,
        "control_folder": os.path.join(temp_dir, "control"),
    },
    beat_schedule_filename=os.path.join(temp_dir, "celerybeat-schedule.db"),
    beat_schedule={
        "test-task": {
            "task": "test_task",
            "schedule": timedelta(seconds=1),  # Run every 1 seconds
        }
    },
)

WORKER_PID = os.getpid()


@app.task(name="test_task")
def test_task():
    os.kill(WORKER_PID, signal.SIGTERM)
