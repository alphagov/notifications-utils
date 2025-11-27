import pytest
from freezegun import freeze_time

from notifications_utils.clients.redis import daily_limit_cache_key


@pytest.mark.parametrize(
    "kwargs, expected_cache_key",
    (
        pytest.param(
            {"notification_type": None, "key_type": None},
            "{sample_service.id}-2016-01-01-count",
            marks=pytest.mark.xfail(raises=ValueError),
        ),
        ({"notification_type": "email", "key_type": None}, "{sample_service.id}-email-2016-01-01-count"),
        ({"notification_type": "sms", "key_type": "normal"}, "{sample_service.id}-sms-2016-01-01-count"),
        ({"notification_type": "letter", "key_type": "normal"}, "{sample_service.id}-letter-2016-01-01-count"),
        ({"notification_type": "email", "key_type": "normal"}, "{sample_service.id}-email-2016-01-01-count"),
        ({"notification_type": "sms", "key_type": "team"}, "{sample_service.id}-sms-2016-01-01-count"),
        ({"notification_type": "letter", "key_type": "team"}, "{sample_service.id}-letter-2016-01-01-count"),
        ({"notification_type": "email", "key_type": "team"}, "{sample_service.id}-email-2016-01-01-count"),
    ),
)
def test_daily_limit_cache_key_for_normal_and_team_keys(sample_service, kwargs, expected_cache_key):
    with freeze_time("2016-01-01 12:00:00.000000"):
        assert daily_limit_cache_key(sample_service.id, **kwargs) == expected_cache_key.format(
            sample_service=sample_service
        )


@pytest.mark.parametrize(
    "kwargs, expected_cache_key",
    (
        pytest.param(
            {"notification_type": None, "key_type": None},
            "{sample_service.id}-test-2016-01-01-count",
            marks=pytest.mark.xfail(raises=ValueError),
        ),
        ({"notification_type": "sms", "key_type": "test"}, "{sample_service.id}-test-sms-2016-01-01-count"),
        ({"notification_type": "letter", "key_type": "test"}, "{sample_service.id}-test-letter-2016-01-01-count"),
        ({"notification_type": "email", "key_type": "test"}, "{sample_service.id}-test-email-2016-01-01-count"),
    ),
)
def test_daily_limit_cache_key_for_test_key(sample_service, kwargs, expected_cache_key):
    with freeze_time("2016-01-01 12:00:00.000000"):
        assert daily_limit_cache_key(sample_service.id, **kwargs) == expected_cache_key.format(
            sample_service=sample_service
        )
