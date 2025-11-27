from datetime import UTC, datetime

from .request_cache import RequestCache  # noqa: F401 (unused import)


def daily_limit_cache_key(service_id, notification_type, key_type=None):
    yyyy_mm_dd = datetime.now(UTC).strftime("%Y-%m-%d")

    if not notification_type:
        raise ValueError("notification_type is required")

    if key_type == "test":
        return f"{service_id}-test-{notification_type}-{yyyy_mm_dd}-count"
    else:
        return f"{service_id}-{notification_type}-{yyyy_mm_dd}-count"
