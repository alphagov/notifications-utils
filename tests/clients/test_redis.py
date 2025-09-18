import pytest
from freezegun import freeze_time

from notifications_utils.clients.redis import daily_limit_cache_key


@pytest.mark.parametrize(
    "kwargs, expected_cache_key",
    (
        pytest.param({}, "{sample_service.id}-2016-01-01-count", marks=pytest.mark.xfail(raises=TypeError)),
        pytest.param(
            {"notification_type": None},
            "{sample_service.id}-2016-01-01-count",
            marks=pytest.mark.xfail(raises=TypeError),
        ),
        ({"notification_type": "sms"}, "{sample_service.id}-sms-2016-01-01-count"),
        ({"notification_type": "letter"}, "{sample_service.id}-letter-2016-01-01-count"),
        ({"notification_type": "email"}, "{sample_service.id}-email-2016-01-01-count"),
    ),
)
def test_daily_limit_cache_key(sample_service, kwargs, expected_cache_key):
    with freeze_time("2016-01-01 12:00:00.000000"):
        assert daily_limit_cache_key(sample_service.id, **kwargs) == expected_cache_key.format(
            sample_service=sample_service
        )
