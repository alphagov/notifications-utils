import contextvars
import os
import time
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


class PoolExpansionCooldownEventletWorker(geventlet.EventletWorker):
    """
    Starting with an initial GreenPool size of `initial_concurrency`, will gradually expand the
    GreenPool size as demanded, though never expanding it more than once within
    `pool_expansion_cooldown_seconds` and to an absolute maximum of `concurrency`.

    If `pool_expansion_min_wait_seconds` is set to a nonzero value, will ensure *any* pool
    expansion will only happen after waiting this amount of time for an existing thread
    slot to be vacated - the intention being to bias new connections towards being accepted
    by processes that already have vacant thread slots.

    Also won't accept a connection until our GreenPool has capacity to handle it.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._pool_expansion_cooldown_seconds = getattr(self.cfg, "pool_expansion_cooldown_seconds", 1.0)
        self._pool_expansion_min_wait_seconds = getattr(self.cfg, "pool_expansion_min_wait_seconds", 0)
        self._initial_concurrency = getattr(self.cfg, "initial_concurrency", 1)

    # based on gunicorn@1299ea9e967a61ae2edebe191082fd169b864c64's _eventlet_serve
    # routine with sections added before and after sock.accept() call
    def eventlet_serve(self, sock, handle, concurrency):
        pool = eventlet.greenpool.GreenPool(self._initial_concurrency)
        server_gt = eventlet.greenthread.getcurrent()

        while True:
            try:
                time_till_cooldown_expiry = max(
                    self._pool_expansion_min_wait_seconds,
                    self._pool_expansion_cooldown_seconds - (time.monotonic() - self.last_expanded),
                )
                if pool.size >= concurrency or time_till_cooldown_expiry > 0:
                    # if we've already reached maximum concurrency, wait indefinitely for a
                    # GreenThread slot to become available, else wait time_till_cooldown_expiry
                    timeout = None if pool.size >= concurrency else time_till_cooldown_expiry

                    if pool.sem.acquire(timeout=timeout):
                        # an existing GreenThread slot has become available - "release" this
                        # semaphore so it can be re-acquired in pool.spawn
                        pool.sem.release()
                    # else it's at least been pool_expansion_cooldown_seconds since we last expanded
                    # the pool, warranting us to proceed and accept a connection

                conn, addr = sock.accept()

                # (re)check if we (still) need to expand the pool to handle this connection
                if pool.sem.counter == 0:
                    # we do
                    pool.resize(pool.size + 1)
                    self.last_expanded = time.monotonic()
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

    def run(self, *args, **kwargs):
        self.last_expanded = time.monotonic()
        super().run(*args, **kwargs)

    def patch(self, *args, **kwargs):
        # _eventlet_serve being a module-level function, we don't really have any choice but to
        # monkey-patch it (or have to totally replace the run() method)
        geventlet._eventlet_serve = self.eventlet_serve
        super().patch(*args, **kwargs)


class NotifyEventletWorker(PoolExpansionCooldownEventletWorker, ContextRecyclingEventletWorker):
    pass
