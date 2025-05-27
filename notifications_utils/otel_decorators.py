import functools
import time

from flask import current_app


def otel(namespace):
    def time_function(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.monotonic()
            try:
                res = func(*args, **kwargs)
                elapsed_time = time.monotonic() - start_time
                current_app.otel_client.incr(
                    "function_call",
                    value=1,
                    attributes={
                        "function": func.__name__,
                        "namespace": namespace,
                    },
                    description="Function call count",
                )
                current_app.otel_client.record(
                    "function_duration_seconds",
                    elapsed_time,
                    attributes={
                        "function": func.__name__,
                        "namespace": namespace,
                    },
                    description="Duration of function in seconds",
                    unit="seconds",
                )

            except Exception as e:
                raise e
            else:
                current_app.logger.debug("%s call %s took %.4f", namespace, func.__name__, elapsed_time)
                return res

        wrapper.__wrapped__.__name__ = func.__name__
        return wrapper

    return time_function
