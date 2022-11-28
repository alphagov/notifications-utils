from datetime import datetime

from .request_cache import RequestCache  # noqa: F401 (unused import)


def daily_limit_cache_key(service_id):
    return f"{service_id}-{datetime.utcnow().strftime('%Y-%m-%d')}-count"


def rate_limit_cache_key(service_id, api_key_type):
    return f"{service_id}-{api_key_type}"
