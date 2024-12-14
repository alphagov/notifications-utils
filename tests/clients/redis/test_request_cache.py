from unittest.mock import MagicMock, call

import pytest

from notifications_utils.clients.redis import RequestCache
from notifications_utils.clients.redis.redis_client import RedisClient


@pytest.fixture(scope="function")
def mocked_redis_client(app):
    app.config["REDIS_ENABLED"] = True
    redis_client = RedisClient()
    redis_client.init_app(app)
    return redis_client


@pytest.fixture
def cache(mocked_redis_client):
    return RequestCache(mocked_redis_client)


@pytest.mark.parametrize(
    "args, kwargs, expected_cache_key",
    (
        ([1, 2, 3], {}, "1-2-3-None-None-None"),
        ([1, 2, 3, 4, 5, 6], {}, "1-2-3-4-5-6"),
        ([1, 2, 3], {"x": 4, "y": 5, "z": 6}, "1-2-3-4-5-6"),
        ([1, 2, 3, 4], {"y": 5}, "1-2-3-4-5-None"),
        (
            [
                "6CE466D0-FD6A-11E5-82F5-E0ACCB9D11A6",
                "B",
                "c",
            ],
            {
                "x": "6ce466d0-fd6a-11e5-82f5-e0accb9d11a6",
                "y": "Y",
                "z": "z",
            },
            # UUIDs get lowercased but other strings keep their original case
            "6ce466d0-fd6a-11e5-82f5-e0accb9d11a6-B-c-6ce466d0-fd6a-11e5-82f5-e0accb9d11a6-Y-z",
        ),
    ),
)
def test_set(
    mocked_redis_client,
    cache,
    args,
    kwargs,
    expected_cache_key,
    mocker,
):
    mock_redis_set = mocker.patch.object(
        mocked_redis_client,
        "set",
    )
    mock_redis_get = mocker.patch.object(
        mocked_redis_client,
        "get",
        return_value=None,
    )

    @cache.set("{a}-{b}-{c}-{x}-{y}-{z}")
    def foo(a, b, c, x=None, y=None, z=None):
        return "bar"

    assert foo(*args, **kwargs) == "bar"

    mock_redis_get.assert_called_once_with(expected_cache_key)

    mock_redis_set.assert_called_once_with(
        expected_cache_key,
        '"bar"',
        ex=2_419_200,
    )


@pytest.mark.parametrize(
    "cache_set_call, expected_redis_client_ttl",
    (
        (0, 0),
        (1, 1),
        (1.111, 1),
        ("2000", 2_000),
    ),
)
def test_set_with_custom_ttl(
    mocked_redis_client,
    cache,
    cache_set_call,
    expected_redis_client_ttl,
    mocker,
):
    mock_redis_set = mocker.patch.object(
        mocked_redis_client,
        "set",
    )
    mocker.patch.object(
        mocked_redis_client,
        "get",
        return_value=None,
    )

    @cache.set("foo", ttl_in_seconds=cache_set_call)
    def foo():
        return "bar"

    foo()

    mock_redis_set.assert_called_once_with(
        "foo",
        '"bar"',
        ex=expected_redis_client_ttl,
    )


def test_raises_if_key_doesnt_match_arguments(cache):
    @cache.set("{baz}")
    def foo(bar):
        pass

    with pytest.raises(KeyError):
        foo(1)

    with pytest.raises(KeyError):
        foo()


@pytest.mark.parametrize(
    "cache_decision, ttl_in_seconds_override, expect_set_call_ttl",
    (
        (False, None, None),
        (True, None, 333),
        (123, None, 333),
        (True, 234, 234),
    ),
)
def test_set_result_wrapper(
    cache_decision, ttl_in_seconds_override, expect_set_call_ttl, mocked_redis_client, cache, mocker
):
    @cache.set("{bar}-xyz", ttl_in_seconds=333)
    def foo(bar):
        return RequestCache.CacheResultWrapper({"blah": f"123-{bar}"}, cache_decision, ttl_in_seconds_override)

    mock_redis_set = mocker.patch.object(
        mocked_redis_client,
        "set",
    )
    mocker.patch.object(
        mocked_redis_client,
        "get",
        return_value=None,
    )

    ret = foo("quack")

    assert ret == {"blah": "123-quack"}

    assert (
        mock_redis_set.mock_calls == []
        if cache_decision is None
        else [mocker.call("quack-xyz", '{"blah": "123-quack"}', ex=expect_set_call_ttl)]
    )


def test_set_result_custom_get_decision(mocked_redis_client, cache, mocker):
    @cache.get_cache_decision.register
    def _(result: float):
        return result > 50

    @cache.get_ttl_in_seconds_override.register
    def _(result: float):
        return int(result) * 2

    @cache.set("{bar}-xyz", ttl_in_seconds=333)
    def foo(bar):
        return bar * 10.0

    mock_redis_set = mocker.patch.object(
        mocked_redis_client,
        "set",
    )
    mocker.patch.object(
        mocked_redis_client,
        "get",
        return_value=None,
    )

    ret = foo(3)

    assert ret == 30.0

    assert mock_redis_set.mock_calls == []

    ret2 = foo(8)

    assert ret2 == 80.0

    assert mock_redis_set.mock_calls == [mocker.call("8-xyz", "80.0", ex=160)]


@pytest.mark.parametrize(
    "args, expected_cache_key",
    (
        (
            (1, 2, 3),
            ("1-2-3"),
        ),
        (
            ("A", "B", "6CE466D0-FD6A-11E5-82F5-E0ACCB9D11A6"),
            ("A-B-6ce466d0-fd6a-11e5-82f5-e0accb9d11a6"),
        ),
    ),
)
def test_get(mocked_redis_client, cache, args, expected_cache_key, mocker):
    mock_redis_get = mocker.patch.object(
        mocked_redis_client,
        "get",
        return_value=b'"bar"',
    )

    @cache.set("{a}-{b}-{c}")
    def foo(a, b, c):
        # This function should not be called because the cache has
        # returned a value
        raise RuntimeError

    assert foo(*args) == "bar"

    mock_redis_get.assert_called_once_with(expected_cache_key)


@pytest.mark.parametrize(
    "args, expected_cache_key",
    (
        (
            (1, 2, 3),
            ("1-2-3"),
        ),
        (
            ("A", "B", "6CE466D0-FD6A-11E5-82F5-E0ACCB9D11A6"),
            ("A-B-6ce466d0-fd6a-11e5-82f5-e0accb9d11a6"),
        ),
    ),
)
def test_delete(mocked_redis_client, cache, args, expected_cache_key, mocker):
    mock_redis_delete = mocker.patch.object(
        mocked_redis_client,
        "delete",
    )

    @cache.delete("{a}-{b}-{c}")
    def foo(a, b, c):
        return "bar"

    assert foo(*args) == "bar"

    expected_call = call(expected_cache_key, raise_exception=True)
    mock_redis_delete.assert_has_calls([expected_call, expected_call])


def test_doesnt_update_api_if_redis_delete_fails(mocked_redis_client, cache, mocker):
    mocker.patch.object(mocked_redis_client, "delete", side_effect=RuntimeError("API update failed"))
    fake_api_call = MagicMock()

    @cache.delete("bar")
    def foo():
        return fake_api_call()

    with pytest.raises(RuntimeError):
        foo()

    fake_api_call.assert_not_called()


def test_delete_by_pattern(mocked_redis_client, cache, mocker):
    mock_redis_delete = mocker.patch.object(
        mocked_redis_client,
        "delete_by_pattern",
    )

    @cache.delete_by_pattern("{a}-{b}-{c}-???")
    def foo(a, b, c):
        return "bar"

    assert foo(1, 2, 3) == "bar"

    expected_call = call("1-2-3-???", raise_exception=True)
    mock_redis_delete.assert_has_calls([expected_call, expected_call])


def test_doesnt_update_api_if_redis_delete_by_pattern_fails(mocked_redis_client, cache, mocker):
    mocker.patch.object(mocked_redis_client, "delete_by_pattern", side_effect=RuntimeError("API update failed"))
    fake_api_call = MagicMock()

    @cache.delete_by_pattern("bar-???")
    def foo():
        return fake_api_call()

    with pytest.raises(RuntimeError):
        foo()

    fake_api_call.assert_not_called()
