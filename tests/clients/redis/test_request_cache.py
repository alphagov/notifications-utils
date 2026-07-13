import json
import time
from datetime import datetime
from unittest.mock import MagicMock

import msgpack
import pytest
from freezegun import freeze_time

from notifications_utils.clients.redis import RequestCache
from notifications_utils.clients.redis.redis_client import RedisClient
from notifications_utils.testing.comparisons import AnySupersetOf


@pytest.fixture(scope="function")
def mocked_redis_client(app):
    app.config["REDIS_ENABLED"] = True
    redis_client = RedisClient()
    redis_client.init_app(app)
    return redis_client


@pytest.fixture
def cache(mocked_redis_client):
    return RequestCache(mocked_redis_client)


@pytest.fixture
def live_cache(redis_client_with_live_instance):
    return RequestCache(redis_client_with_live_instance)


@pytest.mark.parametrize("schema_version", [0, 1])
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
    schema_version,
):
    if schema_version == 0:
        mock_redis_set = mocker.patch.object(
            mocked_redis_client,
            "set",
        )
    else:
        mock_redis_set = mocker.patch.object(mocked_redis_client, "set_if_timestamp_newer")
    mock_redis_get = mocker.patch.object(
        mocked_redis_client,
        "get",
        return_value=None,
    )

    @cache.set("{a}-{b}-{c}-{x}-{y}-{z}", schema_version=schema_version)
    def foo(a, b, c, x=None, y=None, z=None):
        return "bar"

    with freeze_time("2018-7-7 16:00:00"):
        set_time = time.time()
        assert foo(*args, **kwargs) == "bar"

    mock_redis_get.assert_called_once_with(
        expected_cache_key,
        skippable=True,
    )

    if schema_version == 0:
        mock_redis_set.assert_called_once_with(
            expected_cache_key,
            '"bar"',
            ex=2_419_200,
            skippable=True,
        )
    else:
        assert mock_redis_set.call_args_list[0][1] == {"ex": 2_419_200}
        assert msgpack.loads(mock_redis_set.call_args_list[0][0][1]) == {
            "timestamp": set_time,
            "is_tombstone": False,
            "value": msgpack.dumps("bar"),
            "schema_version": 1,
        }


def test_set_if_timestamp_newer(redis_client_with_live_instance, live_cache):

    @live_cache.set("my-key", schema_version=1)
    def interrupting_function():
        return "this was set later than the pesimistic timestamp"

    @live_cache.set("my-key", schema_version=1)
    def foo():
        interrupting_function()
        return "this should not get set"

    assert foo() == "this should not get set"

    assert msgpack.loads(redis_client_with_live_instance.get("my-key")) == AnySupersetOf(
        {
            "value": msgpack.dumps("this was set later than the pesimistic timestamp"),
        }
    )


@pytest.mark.parametrize("schema_version", [0, 1])
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
    schema_version,
):
    if schema_version == 0:
        mock_redis_set = mocker.patch.object(
            mocked_redis_client,
            "set",
        )
    else:
        mock_redis_set = mocker.patch.object(mocked_redis_client, "set_if_timestamp_newer")
    mocker.patch.object(
        mocked_redis_client,
        "get",
        return_value=None,
    )

    @cache.set("foo", ttl_in_seconds=cache_set_call, schema_version=schema_version)
    def foo():
        return "bar"

    foo()

    if schema_version == 0:
        mock_redis_set.assert_called_once_with(
            "foo",
            '"bar"',
            ex=expected_redis_client_ttl,
            skippable=True,
        )
    else:
        assert mock_redis_set.call_args_list[0][1] == {"ex": expected_redis_client_ttl}


@pytest.mark.parametrize("schema_version", [0, 1])
def test_raises_if_key_doesnt_match_arguments(cache, schema_version):
    @cache.set("{baz}", schema_version=schema_version)
    def foo(bar):
        pass

    with pytest.raises(KeyError):
        foo(1)

    with pytest.raises(KeyError):
        foo()


@pytest.mark.parametrize("schema_version", [0, 1])
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
    cache_decision, ttl_in_seconds_override, expect_set_call_ttl, mocked_redis_client, cache, mocker, schema_version
):
    @cache.set("{bar}-xyz", ttl_in_seconds=333, schema_version=schema_version)
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

    if schema_version == 1:
        mocker.patch.object(mocked_redis_client, "set_if_timestamp_newer", return_value=True)

    ret = foo("quack")

    assert ret == {"blah": "123-quack"}

    assert (
        mock_redis_set.mock_calls == []
        if cache_decision is None
        else [mocker.call("quack-xyz", '{"blah": "123-quack"}', ex=expect_set_call_ttl)]
    )


@pytest.mark.parametrize("schema_version", [0, 1])
def test_set_result_custom_get_decision(redis_client_with_live_instance, cache, mocker, schema_version):

    @cache.get_cache_decision.register
    def _(result: float):
        return result > 50

    @cache.get_ttl_in_seconds_override.register
    def _(result: float):
        return int(result) * 2

    @cache.set("{bar}-xyz", ttl_in_seconds=333, schema_version=schema_version)
    def foo(bar):
        return bar * 10.0

    ret = foo(3)

    assert ret == 30.0

    assert not redis_client_with_live_instance.get("3-xyz")

    ret2 = foo(8)

    assert ret2 == 80.0

    if schema_version == 0:
        assert float(redis_client_with_live_instance.get("8-xyz")) == 80.0
    if schema_version == 1:
        assert msgpack.loads(redis_client_with_live_instance.get("8-xyz")) == AnySupersetOf(
            {"is_tombstone": False, "schema_version": 1, "value": msgpack.dumps(80.0)}
        )


@pytest.mark.parametrize("schema_version", [0, 1])
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
def test_get(cache, args, expected_cache_key, mocker, redis_client_with_live_instance, schema_version):

    if schema_version == 0:
        redis_client_with_live_instance.set(expected_cache_key, json.dumps("bar"))
    else:
        redis_client_with_live_instance.set(
            expected_cache_key,
            msgpack.dumps(
                {
                    "timestamp": str(datetime.utcnow()),  # we cannot mock out times that redis lua scripts use
                    "is_tombstone": False,
                    "value": msgpack.dumps("bar"),
                    "schema_version": 1,
                }
            ),
        )

    @cache.set("{a}-{b}-{c}", schema_version=schema_version)
    def foo(a, b, c):
        # This function should not be called because the cache has
        # returned a value
        raise RuntimeError

    assert foo(*args) == "bar"


@pytest.mark.parametrize(
    "args, expected_cache_key, force_delete",
    (
        (
            (1, 2, 3),
            ("1-2-3"),
            True,
        ),
        (
            ("A", "B", "6CE466D0-FD6A-11E5-82F5-E0ACCB9D11A6"),
            ("A-B-6ce466d0-fd6a-11e5-82f5-e0accb9d11a6"),
            True,
        ),
        (
            (1, 2, 3),
            ("1-2-3"),
            False,
        ),
        (
            ("A", "B", "6CE466D0-FD6A-11E5-82F5-E0ACCB9D11A6"),
            ("A-B-6ce466d0-fd6a-11e5-82f5-e0accb9d11a6"),
            False,
        ),
    ),
)
def test_delete(redis_client_with_live_instance, live_cache, args, expected_cache_key, mocker, force_delete):

    if force_delete:
        redis_client_with_live_instance.set(expected_cache_key, "bar")
    else:
        redis_client_with_live_instance.set(
            expected_cache_key,
            msgpack.dumps(
                {
                    "timestamp": str(datetime.utcnow()),  # we cannot mock out times that redis lua scripts use
                    "is_tombstone": False,
                    "value": msgpack.dumps("foo"),
                    "schema_version": 1,
                }
            ),
        )

    @live_cache.delete("{a}-{b}-{c}", force_delete=force_delete)
    def foo(a, b, c):
        return "bar"

    if force_delete:
        assert redis_client_with_live_instance.get(expected_cache_key) == b"bar"
        assert foo(*args) == "bar"
        assert not redis_client_with_live_instance.get(expected_cache_key)
    else:
        assert msgpack.loads(redis_client_with_live_instance.get(expected_cache_key)) == AnySupersetOf(
            {"is_tombstone": False, "value": msgpack.dumps("foo"), "schema_version": 1}
        )
        assert foo(*args) == "bar"
        assert msgpack.loads(redis_client_with_live_instance.get(expected_cache_key)) == AnySupersetOf(
            {"is_tombstone": True}
        )


@pytest.mark.parametrize("force_delete", [True, False])
def test_doesnt_update_api_if_redis_delete_fails(mocked_redis_client, cache, mocker, force_delete):
    mocker.patch.object(mocked_redis_client, "delete", side_effect=RuntimeError("API update failed"))
    mocker.patch.object(mocked_redis_client, "set", side_effect=RuntimeError("API update failed"))
    fake_api_call = MagicMock()

    @cache.delete("bar", force_delete=force_delete)
    def foo():
        return fake_api_call()

    with pytest.raises(RuntimeError):
        foo()

    fake_api_call.assert_not_called()


@pytest.mark.parametrize(
    "force_delete, dict_to_set",
    [
        (True, {"1-2-3": "foo", "1-2-3-bar": "bar"}),
        (
            False,
            {
                "1-2-3": msgpack.dumps(
                    {
                        "timestamp": str(datetime.utcnow()),  # we cannot mock out times that redis lua scripts use
                        "is_tombstone": False,
                        "value": msgpack.dumps("foo"),
                        "schema_version": 1,
                    }
                ),
                "1-2-3-bar": msgpack.dumps(
                    {
                        "timestamp": str(datetime.utcnow()),  # we cannot mock out times that redis lua scripts use
                        "is_tombstone": False,
                        "value": msgpack.dumps("bar"),
                        "schema_version": 1,
                    }
                ),
            },
        ),
    ],
)
def test_delete_by_pattern(redis_client_with_live_instance, live_cache, mocker, force_delete, dict_to_set):

    for k, v in dict_to_set.items():
        if force_delete:
            redis_client_with_live_instance.set(k, v)
        else:
            redis_client_with_live_instance.set_if_timestamp_newer(k, v, ex=0)

    @live_cache.delete_by_pattern("{a}-{b}-{c}-???", force_delete=force_delete)
    def foo(a, b, c):
        return "bar"

    @live_cache.delete_by_pattern("{a}-{b}-{c}", force_delete=force_delete)
    def bar(a, b, c):
        return "foo"

    assert foo(1, 2, 3) == "bar"
    if force_delete:
        assert not redis_client_with_live_instance.get("1-2-3-bar")
        assert redis_client_with_live_instance.get("1-2-3") == b"foo"
    else:
        assert msgpack.loads(redis_client_with_live_instance.get("1-2-3-bar")) == AnySupersetOf({"is_tombstone": True})
        assert msgpack.loads(redis_client_with_live_instance.get("1-2-3")) == AnySupersetOf(
            {"is_tombstone": False, "value": msgpack.dumps("foo"), "schema_version": 1}
        )

    assert bar(1, 2, 3) == "foo"
    if force_delete:
        assert not redis_client_with_live_instance.get("1-2-3")
    else:
        assert msgpack.loads(redis_client_with_live_instance.get("1-2-3")) == AnySupersetOf({"is_tombstone": True})


@pytest.mark.parametrize("force_delete", [True, False])
def test_doesnt_update_api_if_redis_delete_by_pattern_fails(mocked_redis_client, cache, mocker, force_delete):
    mocker.patch.object(mocked_redis_client, "delete_by_pattern", side_effect=RuntimeError("API update failed"))
    mocker.patch.object(mocked_redis_client, "overwrite_by_pattern", side_effect=RuntimeError("API update failed"))
    fake_api_call = MagicMock()

    @cache.delete_by_pattern("bar-???", force_delete=force_delete)
    def foo():
        return fake_api_call()

    with pytest.raises(RuntimeError):
        foo()

    fake_api_call.assert_not_called()
