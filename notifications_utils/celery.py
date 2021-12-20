import time
from contextlib import contextmanager

from celery import Celery, Task
from flask import g, request
from flask.ctx import has_app_context, has_request_context


def make_task(app):
    class NotifyTask(Task):
        abstract = True
        start = None

        @property
        def queue_name(self):
            delivery_info = self.request.delivery_info or {}
            return delivery_info.get('routing_key', 'none')

        @property
        def request_id(self):
            # Note that each header is a direct attribute of the
            # task context (aka "request").
            return self.request.get('notify_request_id')

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
                    "Celery task {task_name} (queue: {queue_name}) took {time}".format(
                        task_name=self.name,
                        queue_name=self.queue_name,
                        time="{0:.4f}".format(elapsed_time)
                    )
                )

                app.statsd_client.timing(
                    "celery.{queue_name}.{task_name}.success".format(
                        task_name=self.name,
                        queue_name=self.queue_name
                    ), elapsed_time
                )

        def on_failure(self, exc, task_id, args, kwargs, einfo):
            # enables request id tracing for these logs
            with self.app_context():
                app.logger.exception(
                    "Celery task {task_name} (queue: {queue_name}) failed".format(
                        task_name=self.name,
                        queue_name=self.queue_name,
                    )
                )

                app.statsd_client.incr(
                    "celery.{queue_name}.{task_name}.failure".format(
                        task_name=self.name,
                        queue_name=self.queue_name
                    )
                )

        def __call__(self, *args, **kwargs):
            # ensure task has flask context to access config, logger, etc
            with self.app_context():
                self.start = time.monotonic()
                return super().__call__(*args, **kwargs)

    return NotifyTask


class NotifyCelery(Celery):
    def init_app(self, app):
        super().__init__(
            task_cls=make_task(app),
        )

        # Make sure this is present upfront to avoid errors later on.
        assert app.statsd_client

        # Configure Celery app with options from the main app config.
        self.conf.update(app.config['CELERY'])

    def send_task(self, name, args=None, kwargs=None, **other_kwargs):
        other_kwargs['headers'] = other_kwargs.get('headers') or {}

        if has_request_context() and hasattr(request, 'request_id'):
            other_kwargs['headers']['notify_request_id'] = request.request_id

        elif has_app_context() and 'request_id' in g:
            other_kwargs['headers']['notify_request_id'] = g.request_id

        return super().send_task(name, args, kwargs, **other_kwargs)
