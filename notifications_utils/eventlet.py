import sys
import time
from collections.abc import Callable


# eventlet's own Timeout class inherits from BaseException instead of
# Exception, which makes more likely that an attempted catch-all
# handler will miss it.
class EventletTimeout(Exception):
    pass


_ns_per_s = 1.0e-9


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
    import flask
    import greenlet
    from eventlet.hubs import get_hub
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

    def account_greenlet_times(event: str, args) -> None:
        """
        Installed as a `greenlet.settrace()` trace hook, will account timings when greenlet context is
        switched, allowing greenlet_thread_time_ns`, `greenlet_perf_counter_ns` and other functions
        based on these to work.
        """
        match args:
            case (origin, target) if event in ("switch", "throw"):
                thread_time_ns = time.thread_time_ns()
                perf_counter_ns = time.perf_counter_ns()

                if hasattr(origin, "_thread_time_ns_atstart"):
                    if not hasattr(origin, "_thread_time_ns_accum"):
                        origin._thread_time_ns_accum = 0
                    thread_time_ns_delta = thread_time_ns - origin._thread_time_ns_atstart
                    origin._thread_time_ns_accum += thread_time_ns_delta
                    origin._thread_time_ns_atstart = None

                    origin._thread_time_ns_max_continuous = max(
                        thread_time_ns_delta, getattr(origin, "_thread_time_ns_max_continuous", 0)
                    )

                if hasattr(origin, "_perf_counter_ns_atstart"):
                    if not hasattr(origin, "_perf_counter_ns_accum"):
                        origin._perf_counter_ns_accum = 0
                    perf_counter_ns_delta = perf_counter_ns - origin._perf_counter_ns_atstart
                    origin._perf_counter_ns_accum += perf_counter_ns_delta
                    origin._perf_counter_ns_atstart = None

                    origin._perf_counter_ns_max_continuous = max(
                        perf_counter_ns_delta, getattr(origin, "_perf_counter_ns_max_continuous", 0)
                    )

                target._thread_time_ns_atstart = thread_time_ns
                target._perf_counter_ns_atstart = perf_counter_ns
                target._context_switch_count = getattr(target, "_context_switch_count", 0) + 1

    def greenlet_thread_time_ns() -> int | None:
        """
        Analogous to time.thread_time_ns, but timer is specific to this *greenlet*, allowing calculation
        of cpu time used by a particular greenlet.

        May return None if insufficient information is yet available to give a sensible answer, or if
        `account_greenlet_times` has not been installed as a trace hook.
        """
        current_greenlet = greenlet.getcurrent()
        if getattr(current_greenlet, "_thread_time_ns_atstart", None) is None:
            return None

        return (time.thread_time_ns() - current_greenlet._thread_time_ns_atstart) + getattr(
            current_greenlet, "_thread_time_ns_accum", 0
        )

    def greenlet_perf_counter_ns() -> int | None:
        """
        Analogous to time.perf_counter_ns, but timer is specific to this *greenlet*, allowing calculation
        of wallclock time spent switched to a particular greenlet. Use case is quite esoteric, as this will
        also include any time our thread is cpu-starved but happened to be switched to this greenlet, but
        could also be used to discover io waits that don't properly yield to the event loop.

        May return None if insufficient information is yet available to give a sensible answer, or if
        `account_greenlet_times` has not been installed as a trace hook.
        """
        current_greenlet = greenlet.getcurrent()
        if getattr(current_greenlet, "_perf_counter_ns_atstart", None) is None:
            return None

        return (time.perf_counter_ns() - current_greenlet._perf_counter_ns_atstart) + getattr(
            current_greenlet, "_perf_counter_ns_accum", 0
        )

    def greenlet_context_switch_count() -> int | None:
        """
        Returns the number of times this greenlet has been switched out of context since creation.

        May return None if insufficient information is yet available to give a sensible answer, or if
        `account_greenlet_times` has not been installed as a trace hook.
        """
        return getattr(greenlet.getcurrent(), "_context_switch_count", None)

    def reset_greenlet_stats() -> None:
        """
        Resets the records on the current greenlet used for
        greenlet_thread_time_ns_max_continuous & greenlet_perf_counter_ns_max_continuous
        """
        current_greenlet = greenlet.getcurrent()

        current_greenlet._thread_time_ns_max_continuous = 0
        current_greenlet._perf_counter_ns_max_continuous = 0

    def greenlet_thread_time_ns_max_continuous() -> int | None:
        """
        Returns the maximum continuous cpu time (at the greenlet level) spent processing
        this greenlet since reset_greenlet_stats was called for this greenlet.

        May return None if insufficient information is yet available to give a sensible answer, or if
        `account_greenlet_times` has not been installed as a trace hook.
        """
        current_greenlet = greenlet.getcurrent()

        if (
            getattr(current_greenlet, "_thread_time_ns_atstart", None) is None
            and getattr(current_greenlet, "_thread_time_ns_max_continuous", None) is None
        ):
            return None

        # the max continuous period could be the one we're currenly *in*
        current_continuous_ns = 0
        if getattr(current_greenlet, "_thread_time_ns_atstart", None) is not None:
            current_continuous_ns = time.thread_time_ns() - current_greenlet._thread_time_ns_atstart

        return max(current_continuous_ns, getattr(current_greenlet, "_thread_time_ns_max_continuous", None) or 0)

    def greenlet_perf_counter_ns_max_continuous() -> int | None:
        """
        Returns the maximum continuous wallclock time spent processing this greenlet since
        reset_greenlet_stats was called for this greenlet.

        May return None if insufficient information is yet available to give a sensible answer, or if
        `account_greenlet_times` has not been installed as a trace hook.
        """
        current_greenlet = greenlet.getcurrent()

        if (
            getattr(current_greenlet, "_perf_counter_ns_atstart", None) is None
            and getattr(current_greenlet, "_perf_counter_ns_max_continuous", None) is None
        ):
            return None

        # the max continuous period could be the one we're currenly *in*
        current_continuous_ns = 0
        if getattr(current_greenlet, "_perf_counter_ns_atstart", None) is not None:
            current_continuous_ns = time.perf_counter_ns() - current_greenlet._perf_counter_ns_atstart

        return max(current_continuous_ns, getattr(current_greenlet, "_perf_counter_ns_max_continuous", None) or 0)

    def _get_greenlet_debug_info(gt: greenlet.greenlet, key_prefix: str = "") -> dict:
        return {
            f"{key_prefix}greenlet_real_time": (
                gt._perf_counter_ns_accum * _ns_per_s if hasattr(gt, "_perf_counter_ns_accum") else None
            ),
            f"{key_prefix}greenlet_cpu_time": (
                gt._thread_time_ns_accum * _ns_per_s if hasattr(gt, "_thread_time_ns_accum") else None
            ),
            f"{key_prefix}greenlet_context_switches": getattr(gt, "_context_switch_count", None),
        }

    def get_main_greenlets_debug_info() -> dict:
        info = _get_greenlet_debug_info(get_hub().greenlet, "hub_")

        server_greenlet = getattr(flask.current_app, "_server_greenlet", None)
        if server_greenlet:
            info.update(_get_greenlet_debug_info(server_greenlet, "server_"))

        return info

else:
    EventletTimeoutMiddleware = None
    account_greenlet_times = None

    greenlet_thread_time_ns = lambda: None  # noqa
    greenlet_perf_counter_ns = lambda: None  # noqa
    reset_greenlet_stats = lambda: None  # noqa
    greenlet_perf_count_ns_max_continuous = lambda: None  # noqa
    greenlet_thread_time_ns_max_continuous = lambda: None  # noqa
    greenlet_context_switch_count = lambda: None  # noqa
    get_main_greenlets_debug_info = lambda: {}  # noqa
