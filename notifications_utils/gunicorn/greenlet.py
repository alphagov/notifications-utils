import contextvars
from collections import deque

import greenlet
from gunicorn.workers.base import Worker
from gunicorn.workers.base_async import AsyncWorker


class ContextRecyclingWorkerMixin(AsyncWorker):
    """
    Because eventlet's `GreenPool` & gevent's `Pool` discard greenlets after they have
    performed a task, to reduce wasteful continual re-creation of thread-local resources
    this class will maintain a pool of thread contexts suitable for reuse with new
    greenlets. In theory at least this means we will never have more thread contexts
    than the maximum number of concurrent greenlets handling connections we've ever
    had.
    """

    context_pool: deque

    def __init__(self, *args, **kwargs):
        self.context_pool = deque()  # a stack of unused thread contexts
        super().__init__(*args, **kwargs)

    def handle(self, *args, **kwargs):
        g = greenlet.getcurrent()
        if self.context_pool:
            # reuse an existing thread context from the pool
            g.gr_context = self.context_pool.pop()

        ret = super().handle(*args, **kwargs)

        # stash potentially-populated thread context in context_pool
        self.context_pool.append(g.gr_context)
        # replace reference to now-stashed context with an empty one
        g.gr_context = contextvars.Context()

        return ret


# The OTel auto-instrumentation has to happen at a very specific part of the
# worker lifecycle: after the event loop hub has been reset post-fork (which
# happens in `EventletWorker.init_process`/`GeventWorker.init_process`), but
# before the WSGI app is initialised. The most natural place to do this is
# just before `load_wsgi` runs, but there's no hook for that, so we need a
# custom worker class.
class OtelAwareWorkerMixin(Worker):
    def load_wsgi(self) -> None:
        import os

        if os.environ.get("OTEL_SERVICE_NAME") is not None:
            from opentelemetry.instrumentation import auto_instrumentation

            from notifications_utils.semconv import set_service_instance_id

            set_service_instance_id()
            auto_instrumentation.initialize()
        super().load_wsgi()
