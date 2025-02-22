import contextvars
import os
from collections import deque

import eventlet
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

class GreenThreadCreationThrottlingEventletWorker(geventlet.EventletWorker):
    greenthread_creation_wait_seconds = 1.0

    def eventlet_serve(self, sock, handle, concurrency):
        pool = eventlet.greenpool.GreenPool(1)
        server_gt = eventlet.greenthread.getcurrent()

        while True:
            try:
                # if we've already reached maximum concurrency, wait indefinitely for a GreenThread
                # slot to become available, otherwise only wait greenthread_creation_wait_seconds
                timeout = self.greenthread_creation_wait_seconds if pool.size < concurrency else None
                if pool.sem.acquire(timeout=timeout):
                    # an existing GreenThread slot has become available - "release" this
                    # semaphore so it can be re-acquired in pool.spawn
                    pool.sem.release()
                # else we've at least waited greenthread_creation_wait_seconds, warranting
                # us to proceed and accept a connection
                conn, addr = sock.accept()

                # (re)check if we (still) need to expand the pool to handle this connection
                if pool.sem.count == 0:
                    # we do
                    pool.resize(pool.size + 1)
                    log_context = {
                        "pool_size": pool.size,
                        "process_": os.getpid(),
                    }
                    self.log.info("Expanded GreenPool size to %(pool_size)s", log_context, extra=log_context)

                gt = pool.spawn(handle, conn, addr)
                gt.link(geventlet._eventlet_stop, server_gt, conn)
                conn, addr, gt = None, None, None
            except eventlet.StopServe:
                sock.close()
                pool.waitall()
                return

    def patch(self, *args, **kwargs):
        geventlet._eventlet_serve = self.eventlet_serve
        super().patch(*args, **kwargs)

