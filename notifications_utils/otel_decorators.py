import functools
import time

from flask import current_app


def otel(namespace, buckets=None):
    if buckets is None:
        buckets = [0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0, float("inf")]

    def time_function(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.monotonic()
            try:
                res = func(*args, **kwargs)
                elapsed_time = time.monotonic() - start_time
                current_app.otel_client.incr(
                    f"function_call_{namespace}_{func.__name__}",
                    value=1,
                    description="Function call count",
                )
                current_app.otel_client.record(
                    f"function_duration_{namespace}_{func.__name__}",
                    elapsed_time,
                    description="Duration of function in seconds",
                    unit="seconds",
                    explicit_bucket_boundaries_advisory=buckets,
                )

            except Exception as e:
                raise e
            else:
                current_app.logger.debug("%s call %s took %.4f", namespace, func.__name__, elapsed_time)
                return res

        wrapper.__wrapped__.__name__ = func.__name__
        return wrapper

    return time_function
