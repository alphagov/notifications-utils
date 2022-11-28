from freezegun import freeze_time

from notifications_utils.clients.redis import (
    daily_limit_cache_key,
    rate_limit_cache_key,
)


def test_daily_limit_cache_key(sample_service):
    with freeze_time("2016-01-01 12:00:00.000000"):
        assert daily_limit_cache_key(sample_service.id) == f"{sample_service.id}-2016-01-01-count"


def test_rate_limit_cache_key(sample_service):
    assert rate_limit_cache_key(sample_service.id, "TEST") == f"{sample_service.id}-TEST"
