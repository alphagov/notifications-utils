import logging
import time
from contextlib import contextmanager
from os import getpid

from celery import Celery, Task
from celery.backends.base import DisabledBackend
from flask import current_app, g, request
from flask.ctx import has_app_context, has_request_context

# from notifications_utils.patch_kombu_sqs import patch_kombu_sqs_send_message_group_id_for_standard


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
            """
            Read the message group id from the current task context.

            Celery reliably exposes custom headers on self.request as top-level keys.
            Message properties may or may not be present depending on kombu/celery versions,
            so we check both.
            """
            # Prefer header (most reliable across celery versions)
            mgid = self.request.get("notify_message_group_id")
            if mgid:
                return mgid

            # Fallback: kombu properties (if available)
            props = self.request.get("properties") or {}
            return props.get("MessageGroupId")

        @contextmanager
        def app_context(self):
            with app.app_context():
                # Add 'request_id' to 'g' so that it gets logged.
                g.request_id = self.request_id

                # Make current task's MessageGroupId available for inheritance
                g.message_group_id = self.message_group_id
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

        def apply_async(self, args=None, kwargs=None, **options):
            """
            Bridge Celery options -> Kombu message properties.

            Your kombu SQS patch reads:
                message["properties"]["MessageGroupId"]

            But Celery does NOT automatically put MessageGroupId there.
            So we move it into `properties` (and mirror into headers for reliability).
            """
            # Pull out caller-supplied MessageGroupId
            mgid = options.pop("MessageGroupId", None)
            print("🔥 APPLY_ASYNC CALLED 🔥", mgid)

            # Optional inheritance: if not supplied, inherit from current Flask context
            # (useful when a task enqueues sub-tasks)
            if not mgid and current_app.config.get("ENABLE_SQS_MESSAGE_GROUP_IDS", True):
                if has_app_context() and getattr(g, "message_group_id", None):
                    mgid = g.message_group_id

            if mgid:
                current_app.logger.info(
                    "Enqueueing celery task with MessageGroupId",
                    extra={"celery_task": self.name, "message_group_id": mgid},
                )

                # Ensure properties dict exists
                properties = options.setdefault("properties", {}) or {}

                # Correct shape: top-level MessageGroupId (what kombu SQS transport expects)
                properties["MessageGroupId"] = mgid

                # Sanitize any accidental nested shape: properties.properties.MessageGroupId
                # This can happen if some caller passes properties={"properties": {...}}.
                nested = properties.get("properties")
                if isinstance(nested, dict) and nested.get("MessageGroupId") and nested.get("MessageGroupId") != mgid:
                    # If there’s disagreement, keep the explicit mgid we computed
                    pass
                elif isinstance(nested, dict) and nested.get("MessageGroupId"):
                    # If nested matches, remove it to avoid emitting properties.properties.*
                    del properties["properties"]

                options["properties"] = properties  # re-attach in case it was None-ish

                # Mirror into headers for runtime access in task context
                headers = options.setdefault("headers", {}) or {}
                headers["notify_message_group_id"] = mgid
                options["headers"] = headers

            props = options.get("properties") or {}
            if isinstance(props.get("properties"), dict) and "MessageGroupId" in props["properties"]:
                current_app.logger.warning(
                    "Nested MessageGroupId detected (properties.properties.MessageGroupId) - flattening applied",
                    extra={"celery_task": self.name},
                )

            return super().apply_async(args=args, kwargs=kwargs, **options)

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


class NotifyCelery(Celery):
    def init_app(self, app):
        # patch_kombu_sqs_send_message_group_id_for_standard()
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

        # ---- MessageGroupId bridge for send_task callers ----
        mgid = other_kwargs.pop("MessageGroupId", None)
        if not mgid and current_app.config.get("ENABLE_SQS_MESSAGE_GROUP_IDS", True):
            if has_app_context() and getattr(g, "message_group_id", None):
                mgid = g.message_group_id

        if mgid:
            props = other_kwargs.get("properties") or {}

            # Correct shape
            props["MessageGroupId"] = mgid

            #  Remove nested shape if some caller created it
            nested = props.get("properties")
            if isinstance(nested, dict) and nested.get("MessageGroupId") == mgid:
                del props["properties"]

            other_kwargs["properties"] = props
            other_kwargs["headers"]["notify_message_group_id"] = mgid

        return super().send_task(name, args, kwargs, **other_kwargs)

    def _get_backend(self):
        # We want it to instantly return a DisabledBackend object if result_backend is None without expending
        # resources in scanning for a none existent backend store.
        if self.conf.result_backend is None:
            return DisabledBackend(app=self)
        return super()._get_backend()
