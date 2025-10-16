import inspect
import logging
import uuid
from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
import redis
from filelock import FileLock, Timeout
from freezegun import freeze_time
import msgpack

from notifications_utils.clients.redis.redis_client import (
    RedisClient,
    StubLock,
    prepare_value,
)


@pytest.fixture(scope="function")
def mocked_redis_pipeline():
    return Mock()


@pytest.fixture
def delete_mock():
    return Mock(return_value=4)


@pytest.fixture(scope="function")
def redis_client_with_live_instance(app, tmp_path_factory):
    root_tmp_dir = tmp_path_factory.getbasetemp().parent
    redis_lock_file = root_tmp_dir / "redis_lock"
    app.config["REDIS_ENABLED"] = True
    app.config["REDIS_URL"] = "redis://localhost:7000/0"
    lock = FileLock(str(redis_lock_file) + ".lock")
    try:
        with lock.acquire(timeout=10):
            redis_client = RedisClient()
            redis_client.init_app(app)
            redis_client.redis_store.flushall()
            return redis_client
    except Timeout as e:
        raise Exception(f"Timeout while waiting for redis lock. Detail: {e}") from e


@pytest.mark.parametrize(
    "pattern, key_value_pairs, number_of_matches",
    [
        (
            "h?llo",
            [
                ("hello", "valid pattern"),
                ("hallo", "valid pattern"),
                ("h3llo", "valid pattern"),
                ("hellllllllo", "invalid pattern"),
            ],
            3,
        ),
        (
            "h[a,e]llo",
            [
                ("hello", "valid pattern"),
                ("hallo", "valid pattern"),
                ("hullo", "invalid pattern"),
                ("hellllllllo", "invalid pattern"),
            ],
            2,
        ),
    ],
)
def test_delete_by_key_script(app, redis_client_with_live_instance, pattern, key_value_pairs, number_of_matches):
    for key, value in key_value_pairs:
        redis_client_with_live_instance.redis_store.set(key, value)
    assert redis_client_with_live_instance.delete_by_pattern(pattern) == number_of_matches


@freeze_time("2001-01-01 12:00:00.000000", auto_tick_seconds=0.1)
def test_decrement_correct_number_of_tokens_for_multiple_calls_within_replenishment_interval(
    app, redis_client_with_live_instance
):
    key = "rate-limit-test-key"
    replenish_per_sec = 1
    bucket_max = 100
    bucket_min = -100
    redis_client_with_live_instance.get_remaining_bucket_tokens(key, replenish_per_sec, bucket_max, bucket_min)
    redis_client_with_live_instance.get_remaining_bucket_tokens(key, replenish_per_sec, bucket_max, bucket_min)
    tokens_remaining = redis_client_with_live_instance.get_remaining_bucket_tokens(
        key, replenish_per_sec, bucket_max, bucket_min
    )
    assert tokens_remaining == 97


@freeze_time("2001-01-01 12:00:00.000000", auto_tick_seconds=0.1)
def test_do_not_decrement_below_bucket_min(app, redis_client_with_live_instance):
    key = "rate-limit-test-key"
    replenish_per_sec = 1
    bucket_max = 1
    bucket_min = -1
    redis_client_with_live_instance.get_remaining_bucket_tokens(key, replenish_per_sec, bucket_max, bucket_min)
    redis_client_with_live_instance.get_remaining_bucket_tokens(key, replenish_per_sec, bucket_max, bucket_min)
    tokens_remaining = redis_client_with_live_instance.get_remaining_bucket_tokens(
        key, replenish_per_sec, bucket_max, bucket_min
    )
    assert tokens_remaining == -1


@freeze_time("2001-01-01 12:00:00.000000", auto_tick_seconds=0.1)
def test_bucket_replenishment_tops_up_bucket_after_interval(app, redis_client_with_live_instance):
    key = "rate-limit-test-key"
    replenish_per_sec = 5
    bucket_max = 100
    bucket_min = -100
    redis_client_with_live_instance.get_remaining_bucket_tokens(key, replenish_per_sec, bucket_max, bucket_min)
    redis_client_with_live_instance.get_remaining_bucket_tokens(key, replenish_per_sec, bucket_max, bucket_min)
    tokens_remaining = redis_client_with_live_instance.get_remaining_bucket_tokens(
        key, replenish_per_sec, bucket_max, bucket_min
    )
    assert tokens_remaining == 98

def test_set_timestamp_if_newer(redis_client_with_live_instance):
    key = "test-key"
    old_value = msgpack.dumps(
        {
            "timestamp": datetime.fromisoformat("2001-01-01 12:00:00.000000").timestamp(),
            "is_tombstone": False,
            "value": msgpack.dumps("foo"),
            "schema_version": 1,
        }
    )
    new_value = msgpack.dumps(
        {
            "timestamp": datetime.fromisoformat("2002-01-01 12:00:00.000000").timestamp(),
            "is_tombstone": False,
            "value": msgpack.dumps("bar"),
            "schema_version": 1,
        }
    )
    old = redis_client_with_live_instance.set_if_timestamp_newer(key, old_value, ex = 30000000)
    assert old
    new = redis_client_with_live_instance.set_if_timestamp_newer(key, new_value, ex = 30000000)
    assert new
    cached_value = redis_client_with_live_instance.get(key)
    cached_value_dict = msgpack.loads(cached_value)
    assert msgpack.loads(cached_value_dict.get("value")) == "bar"
    assert cached_value_dict.get("timestamp") == datetime.fromisoformat("2002-01-01 12:00:00.000000").timestamp()

@pytest.fixture(scope="function")
def mocked_redis_client(app, mocked_redis_pipeline, delete_mock, mocker):
    app.config["REDIS_ENABLED"] = True

    redis_client = RedisClient()
    redis_client.init_app(app)

    mocker.patch.object(redis_client.redis_store, "get", return_value=100)
    mocker.patch.object(redis_client.redis_store, "set")
    mocker.patch.object(redis_client.redis_store, "incr")
    mocker.patch.object(redis_client.redis_store, "decrby")
    mocker.patch.object(redis_client.redis_store, "delete")
    mocker.patch.object(redis_client.redis_store, "pipeline", return_value=mocked_redis_pipeline)

    mocker.patch.object(redis_client, "scripts", {"delete-keys-by-pattern": delete_mock})

    mocker.patch.object(
        redis_client.redis_store,
        "hgetall",
        return_value={b"template-1111": b"8", b"template-2222": b"8"},
    )

    return redis_client


@pytest.fixture
def failing_redis_client(mocked_redis_client, delete_mock):
    mocked_redis_client.redis_store.get.side_effect = Exception("get failed")
    mocked_redis_client.redis_store.set.side_effect = Exception("set failed")
    mocked_redis_client.redis_store.incr.side_effect = Exception("incr failed")
    mocked_redis_client.redis_store.decrby.side_effect = Exception("decrby failed")
    mocked_redis_client.redis_store.pipeline.side_effect = Exception("pipeline failed")
    mocked_redis_client.redis_store.delete.side_effect = Exception("delete failed")
    delete_mock.side_effect = Exception("delete by pattern failed")
    return mocked_redis_client


def test_should_not_raise_exception_if_raise_set_to_false(app, caplog, failing_redis_client):
    with caplog.at_level(logging.ERROR):
        assert failing_redis_client.get("get_key") is None
        assert failing_redis_client.set("set_key", "set_value") is None
        assert failing_redis_client.incr("incr_key") is None
        assert failing_redis_client.decrby("decrby_key", 5) is None
        assert failing_redis_client.exceeded_rate_limit("rate_limit_key", 100, 100) is False
        assert failing_redis_client.delete("delete_key") is None
        assert failing_redis_client.delete("a", "b", "c") is None
        assert failing_redis_client.delete_by_pattern("pattern") == 0

    assert caplog.messages == [
        "Redis error performing get on get_key",
        "Redis error performing set on set_key",
        "Redis error performing incr on incr_key",
        "Redis error performing decrby on decrby_key",
        "Redis error performing rate-limit-pipeline on rate_limit_key",
        "Redis error performing delete on delete_key",
        "Redis error performing delete on a, b, c",
        "Redis error performing delete-by-pattern on pattern",
    ]


def test_should_raise_exception_if_raise_set_to_true(
    app,
    failing_redis_client,
):
    with pytest.raises(Exception) as e:
        failing_redis_client.get("test", raise_exception=True)
    assert str(e.value) == "get failed"

    with pytest.raises(Exception) as e:
        failing_redis_client.set("test", "test", raise_exception=True)
    assert str(e.value) == "set failed"

    with pytest.raises(Exception) as e:
        failing_redis_client.incr("test", raise_exception=True)
    assert str(e.value) == "incr failed"

    with pytest.raises(Exception) as e:
        failing_redis_client.decrby("test", 7, raise_exception=True)
    assert str(e.value) == "decrby failed"

    with pytest.raises(Exception) as e:
        failing_redis_client.exceeded_rate_limit("test", 100, 200, raise_exception=True)
    assert str(e.value) == "pipeline failed"

    with pytest.raises(Exception) as e:
        failing_redis_client.delete("test", raise_exception=True)
    assert str(e.value) == "delete failed"

    with pytest.raises(Exception) as e:
        failing_redis_client.delete_by_pattern("pattern", raise_exception=True)
    assert str(e.value) == "delete by pattern failed"


def test_should_not_call_if_not_enabled(mocked_redis_client, delete_mock):
    mocked_redis_client.active = False

    assert mocked_redis_client.get("get_key") is None
    assert mocked_redis_client.set("set_key", "set_value") is None
    assert mocked_redis_client.incr("incr_key") is None
    assert mocked_redis_client.decrby("decrby_key", 5) is None
    assert mocked_redis_client.exceeded_rate_limit("rate_limit_key", 100, 100) is False
    assert mocked_redis_client.delete("delete_key") is None
    assert mocked_redis_client.delete_by_pattern("pattern") == 0

    mocked_redis_client.redis_store.get.assert_not_called()
    mocked_redis_client.redis_store.set.assert_not_called()
    mocked_redis_client.redis_store.incr.assert_not_called()
    mocked_redis_client.redis_store.delete.assert_not_called()
    mocked_redis_client.redis_store.pipeline.assert_not_called()
    delete_mock.assert_not_called()


def test_should_call_set_if_enabled(mocked_redis_client):
    mocked_redis_client.set("key", "value")
    mocked_redis_client.redis_store.set.assert_called_with("key", "value", None, None, False, False)


def test_should_call_get_if_enabled(mocked_redis_client):
    assert mocked_redis_client.get("key") == 100
    mocked_redis_client.redis_store.get.assert_called_with("key")


@freeze_time("2001-01-01 12:00:00.000000")
def test_exceeded_rate_limit_should_add_correct_calls_to_the_pipe(mocked_redis_client, mocked_redis_pipeline):
    mocked_redis_client.exceeded_rate_limit("key", 100, 100)
    assert mocked_redis_client.redis_store.pipeline.called
    mocked_redis_pipeline.zadd.assert_called_with("key", {978350400.0: 978350400.0})
    mocked_redis_pipeline.zremrangebyscore.assert_called_with("key", "-inf", 978350300.0)
    mocked_redis_pipeline.zcard.assert_called_with("key")
    mocked_redis_pipeline.expire.assert_called_with("key", 100)
    assert mocked_redis_pipeline.execute.called


@freeze_time("2001-01-01 12:00:00.000000")
def test_exceeded_rate_limit_should_fail_request_if_over_limit(mocked_redis_client, mocked_redis_pipeline):
    mocked_redis_pipeline.execute.return_value = [True, True, 100, True]
    assert mocked_redis_client.exceeded_rate_limit("key", 99, 100)


@freeze_time("2001-01-01 12:00:00.000000")
def test_exceeded_rate_limit_should_allow_request_if_not_over_limit(mocked_redis_client, mocked_redis_pipeline):
    mocked_redis_pipeline.execute.return_value = [True, True, 100, True]
    assert not mocked_redis_client.exceeded_rate_limit("key", 101, 100)


@freeze_time("2001-01-01 12:00:00.000000")
def test_exceeded_rate_limit_not_exceeded(mocked_redis_client, mocked_redis_pipeline):
    mocked_redis_pipeline.execute.return_value = [True, True, 80, True]
    assert not mocked_redis_client.exceeded_rate_limit("key", 90, 100)


def test_exceeded_rate_limit_should_not_call_if_not_enabled(mocked_redis_client, mocked_redis_pipeline):
    mocked_redis_client.active = False

    assert not mocked_redis_client.exceeded_rate_limit("key", 100, 100)
    assert not mocked_redis_client.redis_store.pipeline.called


def test_delete(mocked_redis_client):
    key = "hash-key"
    mocked_redis_client.delete(key)
    mocked_redis_client.redis_store.delete.assert_called_with(key)


def test_delete_multi(mocked_redis_client):
    mocked_redis_client.delete("a", "b", "c")
    mocked_redis_client.redis_store.delete.assert_called_with("a", "b", "c")


@pytest.mark.parametrize(
    "input,output",
    [
        (b"asdf", b"asdf"),
        ("asdf", "asdf"),
        (0, 0),
        (1.2, 1.2),
        (uuid.UUID(int=0), "00000000-0000-0000-0000-000000000000"),
        pytest.param({"a": 1}, None, marks=pytest.mark.xfail(raises=ValueError)),
        pytest.param(datetime.now(UTC), None, marks=pytest.mark.xfail(raises=ValueError)),
    ],
)
def test_prepare_value(input, output):
    assert prepare_value(input) == output


def test_delete_by_pattern(mocked_redis_client, delete_mock):
    ret = mocked_redis_client.delete_by_pattern("foo")
    assert ret == 4
    delete_mock.assert_called_once_with(args=["foo"])


def test_get_redis_lock_returns_lock_with_kwargs(mocked_redis_client):
    lock = mocked_redis_client.get_lock("lock_name", blocking=True)
    assert isinstance(lock, redis.lock.Lock)
    assert lock.redis == mocked_redis_client.redis_store
    assert lock.name == "lock_name"
    assert lock.blocking is True


def test_get_redis_lock_returns_stub_if_redis_not_enabled(mocked_redis_client):
    mocked_redis_client.active = False

    lock = mocked_redis_client.get_lock("lock_name", blocking=True)
    assert isinstance(lock, StubLock)

    assert not lock.locked()
    assert not lock.owned()
    # test context manager changes values of locked/owned
    with lock:
        assert lock.locked()
        assert lock.owned()


def test_redis_stub_lock_function_signatures_match():
    lock_methods = dict(inspect.getmembers(redis.lock.Lock, inspect.isfunction))
    stub_methods = dict(inspect.getmembers(StubLock, inspect.isfunction))

    # these methods are de-facto private methods (they don't have docstrings and aren't
    # mentioned in the redis-py docs) so lets not commit to mocking them and testing them
    lock_methods_to_test = lock_methods.keys() - {
        "do_acquire",
        "do_extend",
        "do_reacquire",
        "do_release",
        "register_scripts",
    }

    missing_methods = lock_methods_to_test - stub_methods.keys()
    assert not missing_methods, f"StubLock has missing methods (testing against redis=={redis.__version__})"

    for fn_name in lock_methods_to_test:
        lock_sig = inspect.signature(lock_methods[fn_name])
        stub_sig = inspect.signature(stub_methods[fn_name])
        assert lock_sig.parameters == stub_sig.parameters, f"(testing StubLock against redis=={redis.__version__})"


def test_decrby(mocked_redis_client):
    key = "hash-key"
    mocked_redis_client.decrby(key, 10)
    mocked_redis_client.redis_store.decrby.assert_called_with(key, 10)
