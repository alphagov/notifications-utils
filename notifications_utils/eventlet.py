import sys
from collections.abc import Callable


# eventlet's own Timeout class inherits from BaseException instead of
# Exception, which makes more likely that an attempted catch-all
# handler will miss it.
class EventletTimeout(Exception):
    pass


# eventlet detection cribbed from
# https://github.com/celery/kombu/blob/74779a8078ab318a016ca107249e59f8c8063ef9/kombu/utils/compat.py#L38
using_eventlet = False
if "eventlet" in sys.modules:
    import socket

    try:
        from eventlet.patcher import is_monkey_patched
    except ImportError:
        pass
    else:
        if is_monkey_patched(socket):
            using_eventlet = True

if using_eventlet:
    from eventlet.timeout import Timeout

    class EventletTimeoutMiddleware:
        """
        A WSGI middleware that will raise `exception` after `timeout_seconds` of request
        processing, *but only when* the next I/O context switch occurs.
        """

        _app: Callable
        _timeout_seconds: float
        _exception: BaseException

        def __init__(
            self,
            app: Callable,
            timeout_seconds: float = 30,
            exception: BaseException = EventletTimeout,
        ):
            self._app = app
            self._timeout_seconds = timeout_seconds
            self._exception = exception

        def __call__(self, *args, **kwargs):
            with Timeout(self._timeout_seconds, exception=self._exception):
                return self._app(*args, **kwargs)

else:
    EventletTimeoutMiddleware = None
