import logging
import time
from contextlib import contextmanager
from os import getpid

from celery import Celery, Task
from celery.backends.base import DisabledBackend
from flask import current_app, g, request
from flask.ctx import has_app_context, has_request_context


def make_task(app):
    class NotifyTask(Task):
        abstract = True
        start = None

        def __init__(self, *args, **kwargs):
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

        @property
        def message_group_id(self):
            return self.request.get("notify_message_group_id")

        @contextmanager
        def app_context(self):
            with app.app_context():
                # Add 'request_id' to 'g' so that it gets logged.
                g.request_id = self.request_id
                yield

        def on_success(self, retval, task_id, args, kwargs):
            # enables request id tracing for these logs
            with self.app_context():
                elapsed_time = time.monotonic() - self.start

                app.logger.info(
                    "Celery task %s (queue: %s) took %.4f",
                    self.name,
                    self.queue_name,
                    elapsed_time,
                    extra={
                        "celery_task": self.name,
                        "celery_task_id": self.request.id,
                        "queue_name": self.queue_name,
                        "retry_number": self.request.retries,
                        "duration": elapsed_time,
                        # avoid name collision with LogRecord's own `process` attribute
                        "process_": getpid(),
                    },
                )

                app.statsd_client.timing(
                    f"celery.{self.queue_name}.{self.name}.success",
                    elapsed_time,
                )

        def on_retry(self, exc, task_id, args, kwargs, einfo):
            # enables request id tracing for these logs
            with self.app_context():
                elapsed_time = time.monotonic() - self.start

                app.logger.warning(
                    "Celery task %s (queue: %s) failed for retry after %.4f",
                    self.name,
                    self.queue_name,
                    elapsed_time,
                    exc_info=True,
                    extra={
                        "celery_task": self.name,
                        "celery_task_id": self.request.id,
                        "queue_name": self.queue_name,
                        "retry_number": self.request.retries,
                        "duration": elapsed_time,
                        # avoid name collision with LogRecord's own `process` attribute
                        "process_": getpid(),
                    },
                )

                app.statsd_client.timing(
                    f"celery.{self.queue_name}.{self.name}.retry",
                    elapsed_time,
                )

        def on_failure(self, exc, task_id, args, kwargs, einfo):
            # enables request id tracing for these logs
            with self.app_context():
                elapsed_time = time.monotonic() - self.start

                app.logger.exception(
                    "Celery task %s (queue: %s) failed after %.4f",
                    self.name,
                    self.queue_name,
                    elapsed_time,
                    extra={
                        "celery_task": self.name,
                        "celery_task_id": self.request.id,
                        "queue_name": self.queue_name,
                        "retry_number": self.request.retries,
                        "duration": elapsed_time,
                        # avoid name collision with LogRecord's own `process` attribute
                        "process_": getpid(),
                    },
                )

                app.statsd_client.incr(f"celery.{self.queue_name}.{self.name}.failure")

        def __call__(self, *args, **kwargs):
            # ensure task has flask context to access config, logger, etc
            with self.app_context():
                self.start = time.monotonic()

                if self.request.id is not None:
                    # we're not being called synchronously
                    app.logger.log(
                        self.early_log_level,
                        "Celery task %s (queue: %s) started",
                        self.name,
                        self.queue_name,
                        extra={
                            "celery_task": self.name,
                            "celery_task_id": self.request.id,
                            "queue_name": self.queue_name,
                            "retry_number": self.request.retries,
                            # avoid name collision with LogRecord's own `process` attribute
                            "process_": getpid(),
                        },
                    )

                return super().__call__(*args, **kwargs)

    return NotifyTask


_fallback_logger = logging.Logger(__name__)


class NotifyCelery(Celery):
    def init_app(self, app):
        super().__init__(
            task_cls=make_task(app),
        )

        # Make sure this is present upfront to avoid errors later on.
        assert app.statsd_client

        # Configure Celery app with options from the main app config.
        self.conf.update(app.config["CELERY"])

    def send_task(self, name, args=None, kwargs=None, **other_kwargs):
        other_kwargs["headers"] = other_kwargs.get("headers") or {}

        if has_request_context() and hasattr(request, "request_id"):
            other_kwargs["headers"]["notify_request_id"] = request.request_id

        elif has_app_context() and "request_id" in g:
            other_kwargs["headers"]["notify_request_id"] = g.request_id

        if "MessageGroupId" in other_kwargs and not other_kwargs["MessageGroupId"]:
            # this is likely to be unintentional, perhaps a call site expecting to be able to
            # propagate a group id that isn't present in some cases
            extra = {
                "celery_task": name,
            }
            ((has_app_context() and current_app.logger) or _fallback_logger).warning(
                "MessageGroupId argument specified explicitly with empty value when calling task %(celery_task)s",
                extra,
                extra=extra,
            )

        if has_app_context() and not current_app.config.get("ENABLE_SQS_MESSAGE_GROUP_IDS", True):
            other_kwargs.pop("MessageGroupId", None)

        # kombu doesn't fetch the MessageGroupId from received SQS messages, so we also need to
        # explicitly annotate this on as a header to allow downstream tasks to propagate it
        other_kwargs["headers"]["notify_message_group_id"] = other_kwargs.get("MessageGroupId")

        return super().send_task(name, args, kwargs, **other_kwargs)

    def _get_backend(self):
        # We want it to instantly return a DisabledBackend object if result_backend is None without expending
        # resources in scanning for a none existent backend store.
        if self.conf.result_backend is None:
            return DisabledBackend(app=self)
        return super()._get_backend()
