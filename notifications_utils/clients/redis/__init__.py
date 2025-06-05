from datetime import UTC, datetime

from .request_cache import RequestCache  # noqa: F401 (unused import)


def daily_limit_cache_key(service_id, notification_type):
    yyyy_mm_dd = datetime.now(UTC).strftime("%Y-%m-%d")

    if not notification_type:
        raise TypeError("notification_type is required")

    return f"{service_id}-{notification_type}-{yyyy_mm_dd}-count"


def rate_limit_cache_key(service_id, api_key_type):
    return f"{service_id}-{api_key_type}"
