import contextvars
from collections import deque

import greenlet
from gunicorn.workers import geventlet


class ContextRecyclingEventletWorker(geventlet.EventletWorker):
    """
    Because eventlet's GreenPool discards GreenThreads after they have performed a task,
    to reduce wasteful continual re-creation of thread-local resources this class will
    maintain a pool of thread contexts suitable for reuse with new GreenThreads. In
    theory at least this means we will never have more thread contexts than the maximum
    number of concurrent GreenThreads handling connections we've ever had.
    """

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
