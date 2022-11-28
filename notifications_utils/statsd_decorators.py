import functools
import time

from flask import current_app


def statsd(namespace):
    def time_function(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.monotonic()
            try:
                res = func(*args, **kwargs)
                elapsed_time = time.monotonic() - start_time
                current_app.statsd_client.incr(f"{namespace}.{func.__name__}")
                current_app.statsd_client.timing(f"{namespace}.{func.__name__}", elapsed_time)

            except Exception as e:
                raise e
            else:
                current_app.logger.debug(f"{namespace} call {func.__name__} took {elapsed_time:.4f}")
                return res

        wrapper.__wrapped__.__name__ = func.__name__
        return wrapper

    return time_function
