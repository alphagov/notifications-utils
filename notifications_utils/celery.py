import logging
import time
from contextlib import contextmanager
from os import getpid

from celery import Celery, Task
from flask import g, request
from flask.ctx import has_app_context, has_request_context
from opentelemetry.instrumentation.celery import CeleryInstrumentor


class NotifyTask(Task):
    abstract = True
    start = None

    def __init__(self, app, *args, **kwargs):
        self.custom_app = app
        # custom task-decorator arguments magically get applied as class attributes (!),
        # provide a default if this is missing
        self.early_log_level = getattr(self, "early_log_level", logging.INFO)
        super().__init__(*args, **kwargs)

    @property
    def queue_name(self):
        delivery_info = self.request.delivery_info or {}
        return delivery_info.get("routing_key", "none")

    @property
    def request_id(self):
        # Note that each header is a direct attribute of the
        # task context (aka "request").
        return self.request.get("notify_request_id") or self.request.id

    @contextmanager
    def app_context(self):
        with self.custom_app.app_context():
            # Add 'request_id' to 'g' so that it gets logged.
            g.request_id = self.request_id
            yield

    def on_success(self, retval, task_id, args, kwargs):
        # enables request id tracing for these logs
        with self.app_context():
            elapsed_time = time.monotonic() - self.start

            self.custom_app.logger.info(
                "Celery task %s (queue: %s) took %.4f",
                self.name,
                self.queue_name,
                elapsed_time,
                extra={
                    "celery_task": self.name,
                    "celery_task_id": self.request.id,
                    "queue_name": self.queue_name,
                    "time_taken": elapsed_time,
                    # avoid name collision with LogRecord's own `process` attribute
                    "process_": getpid(),
                },
            )

            if hasattr(self.custom_app, "statsd_client") and self.custom_app.statsd_client:
                self.custom_app.statsd_client.timing(
                    f"celery.{self.queue_name}.{self.name}.success",
                    elapsed_time,
                )

            # OpenTelemetry metric
            if hasattr(self.custom_app, "otel_client") and self.custom_app.otel_client:
                self.custom_app.otel_client.incr(
                    "celery_task_success_total",
                    value=1,
                    attributes={"task": self.name, "queue": self.queue_name},
                    description="Celery task successes",
                    unit="1",
                )
                self.custom_app.otel_client.record(
                    "celery_task_success_duration_seconds",
                    value=elapsed_time,
                    attributes={"task": self.name, "queue": self.queue_name},
                    description="Celery task success duration in seconds",
                    unit="s",
                )

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        # enables request id tracing for these logs
        with self.app_context():
            elapsed_time = time.monotonic() - self.start

            self.custom_app.logger.warning(
                "Celery task %s (queue: %s) failed for retry after %.4f",
                self.name,
                self.queue_name,
                elapsed_time,
                extra={
                    "celery_task": self.name,
                    "celery_task_id": self.request.id,
                    "queue_name": self.queue_name,
                    "time_taken": elapsed_time,
                    # avoid name collision with LogRecord's own `process` attribute
                    "process_": getpid(),
                },
            )

            if hasattr(self.custom_app, "statsd_client") and self.custom_app.statsd_client:
                self.custom_app.statsd_client.timing(
                    f"celery.{self.queue_name}.{self.name}.retry",
                    elapsed_time,
                )

            if hasattr(self.custom_app, "otel_client") and self.custom_app.otel_client:
                self.custom_app.otel_client.incr(
                    "celery_task_retry_total",
                    value=1,
                    attributes={"task": self.name, "queue": self.queue_name},
                    description="Celery task retries",
                    unit="1",
                )
                self.custom_app.otel_client.record(
                    "celery_task_retry_duration_seconds",
                    value=elapsed_time,
                    attributes={"task": self.name, "queue": self.queue_name},
                    description="Celery task retry duration in seconds",
                    unit="s",
                )

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        # enables request id tracing for these logs
        with self.app_context():
            elapsed_time = time.monotonic() - self.start

            self.custom_app.logger.exception(
                "Celery task %s (queue: %s) failed after %.4f",
                self.name,
                self.queue_name,
                elapsed_time,
                extra={
                    "celery_task": self.name,
                    "celery_task_id": self.request.id,
                    "queue_name": self.queue_name,
                    "time_taken": elapsed_time,
                    # avoid name collision with LogRecord's own `process` attribute
                    "process_": getpid(),
                },
            )

            if hasattr(self.custom_app, "statsd_client") and self.custom_app.statsd_client:
                self.custom_app.statsd_client.incr(f"celery.{self.queue_name}.{self.name}.failure")

            if hasattr(self.custom_app, "otel_client") and self.custom_app.otel_client:
                self.custom_app.otel_client.incr(
                    "celery_task_failure_total",
                    value=1,
                    attributes={"task": self.name, "queue": self.queue_name},
                    description="Celery task failures",
                    unit="1",
                )

    def __call__(self, *args, **kwargs):
        # ensure task has flask context to access config, logger, etc
        with self.app_context():
            self.start = time.monotonic()

            if self.request.id is not None:
                # we're not being called synchronously
                self.custom_app.logger.log(
                    self.early_log_level,
                    "Celery task %s (queue: %s) started",
                    self.name,
                    self.queue_name,
                    extra={
                        "celery_task": self.name,
                        "celery_task_id": self.request.id,
                        "queue_name": self.queue_name,
                        # avoid name collision with LogRecord's own `process` attribute
                        "process_": getpid(),
                    },
                )

            return super().__call__(*args, **kwargs)


def make_task(app):
    class AppBoundNotifyTask(NotifyTask):
        def __init__(self, *args, **kwargs):
            super().__init__(app, *args, **kwargs)

    return AppBoundNotifyTask


class NotifyCelery(Celery):
    def init_app(self, app):
        super().__init__(
            task_cls=make_task(app),
        )

        if hasattr(app, "otel_client") and app.otel_client:
            CeleryInstrumentor().instrument()

        # Configure Celery app with options from the main app config.
        self.conf.update(app.config["CELERY"])

    def send_task(self, name, args=None, kwargs=None, **other_kwargs):
        other_kwargs["headers"] = other_kwargs.get("headers") or {}

        if has_request_context() and hasattr(request, "request_id"):
            other_kwargs["headers"]["notify_request_id"] = request.request_id

        elif has_app_context() and "request_id" in g:
            other_kwargs["headers"]["notify_request_id"] = g.request_id

        return super().send_task(name, args, kwargs, **other_kwargs)
