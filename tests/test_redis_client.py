import uuid
from datetime import datetime
from unittest.mock import Mock, call

import pytest
from freezegun import freeze_time

from notifications_utils.clients.redis import (
    daily_limit_cache_key,
    rate_limit_cache_key,
)
from notifications_utils.clients.redis.redis_client import (
    RedisClient,
    prepare_value,
)


@pytest.fixture(scope='function')
def mocked_redis_pipeline():
    return Mock()


@pytest.fixture(scope='function')
def mocked_redis_client(app, mocked_redis_pipeline, mocker):
    app.config['REDIS_ENABLED'] = True
    return build_redis_client(app, mocked_redis_pipeline, mocker)


def build_redis_client(app, mocked_redis_pipeline, mocker):
    redis_client = RedisClient()
    redis_client.init_app(app)
    mocker.patch.object(redis_client.redis_store, 'get', return_value=100)
    mocker.patch.object(redis_client.redis_store, 'set')
    mocker.patch.object(redis_client.redis_store, 'hincrby')
    mocker.patch.object(redis_client.redis_store, 'hgetall',
                        return_value={b'template-1111': b'8', b'template-2222': b'8'})
    mocker.patch.object(redis_client.redis_store, 'hmset')
    mocker.patch.object(redis_client.redis_store, 'expire')
    mocker.patch.object(redis_client.redis_store, 'delete')
    mocker.patch.object(redis_client.redis_store, 'pipeline', return_value=mocked_redis_pipeline)

    return redis_client


def test_should_not_raise_exception_if_raise_set_to_false(app, caplog, mocker):
    mock_logger = mocker.patch('flask.Flask.logger')

    app.config['REDIS_ENABLED'] = True
    redis_client = RedisClient()
    redis_client.init_app(app)
    redis_client.redis_store.get = Mock(side_effect=Exception())
    redis_client.redis_store.set = Mock(side_effect=Exception())
    redis_client.redis_store.incr = Mock(side_effect=Exception())
    redis_client.redis_store.pipeline = Mock(side_effect=Exception())
    redis_client.redis_store.expire = Mock(side_effect=Exception())
    redis_client.redis_store.delete = Mock(side_effect=Exception())
    assert redis_client.get('get_key') is None
    assert redis_client.set('set_key', 'set_value') is None
    assert redis_client.incr('incr_key') is None
    assert redis_client.exceeded_rate_limit('rate_limit_key', 100, 100) is False
    assert redis_client.expire('expire_key', 100) is None
    assert redis_client.delete('delete_key') is None
    assert redis_client.delete('a', 'b', 'c') is None
    assert mock_logger.mock_calls == [
        call.exception('Redis error performing get on get_key'),
        call.exception('Redis error performing set on set_key'),
        call.exception('Redis error performing incr on incr_key'),
        call.exception('Redis error performing rate-limit-pipeline on rate_limit_key'),
        call.exception('Redis error performing expire on expire_key'),
        call.exception('Redis error performing delete on delete_key'),
        call.exception('Redis error performing delete on a, b, c'),
    ]


def test_should_raise_exception_if_raise_set_to_true(app):
    app.config['REDIS_ENABLED'] = True
    redis_client = RedisClient()
    redis_client.init_app(app)
    redis_client.redis_store.get = Mock(side_effect=Exception('get failed'))
    redis_client.redis_store.set = Mock(side_effect=Exception('set failed'))
    redis_client.redis_store.incr = Mock(side_effect=Exception('inc failed'))
    redis_client.redis_store.pipeline = Mock(side_effect=Exception('pipeline failed'))
    redis_client.redis_store.expire = Mock(side_effect=Exception('expire failed'))
    redis_client.redis_store.delete = Mock(side_effect=Exception('delete failed'))
    with pytest.raises(Exception) as e:
        redis_client.get('test', raise_exception=True)
    assert str(e.value) == 'get failed'
    with pytest.raises(Exception) as e:
        redis_client.set('test', 'test', raise_exception=True)
    assert str(e.value) == 'set failed'
    with pytest.raises(Exception) as e:
        redis_client.incr('test', raise_exception=True)
    assert str(e.value) == 'inc failed'
    with pytest.raises(Exception) as e:
        redis_client.exceeded_rate_limit('test', 100, 200, raise_exception=True)
    assert str(e.value) == 'pipeline failed'
    with pytest.raises(Exception) as e:
        redis_client.expire('test', 0, raise_exception=True)
    assert str(e.value) == 'expire failed'
    with pytest.raises(Exception) as e:
        redis_client.delete('test', raise_exception=True)
    assert str(e.value) == 'delete failed'


def test_should_not_call_set_if_not_enabled(mocked_redis_client):
    mocked_redis_client.active = False
    assert not mocked_redis_client.set('key', 'value')
    mocked_redis_client.redis_store.set.assert_not_called()


def test_should_call_set_if_enabled(mocked_redis_client):
    mocked_redis_client.set('key', 'value')
    mocked_redis_client.redis_store.set.assert_called_with('key', 'value', None, None, False, False)


def test_should_not_call_get_if_not_enabled(mocked_redis_client):
    mocked_redis_client.active = False
    mocked_redis_client.get('key')
    mocked_redis_client.redis_store.get.assert_not_called()


def test_should_not_call_redis_if_not_enabled_for_rate_limit_check(mocked_redis_client):
    mocked_redis_client.active = False
    mocked_redis_client.exceeded_rate_limit('key', 100, 200)
    mocked_redis_client.redis_store.pipeline.assert_not_called()


def test_should_call_get_if_enabled(mocked_redis_client):
    assert mocked_redis_client.get('key') == 100
    mocked_redis_client.redis_store.get.assert_called_with('key')


def test_should_build_cache_key_service_and_action(sample_service):
    with freeze_time("2016-01-01 12:00:00.000000"):
        assert daily_limit_cache_key(sample_service.id) == '{}-2016-01-01-count'.format(sample_service.id)


def test_should_build_daily_limit_cache_key(sample_service):
    assert rate_limit_cache_key(sample_service.id, 'TEST') == '{}-TEST'.format(sample_service.id)


def test_decrement_hash_value_should_decrement_value_by_one_for_key(mocked_redis_client):
    key = '12345'
    value = "template-1111"

    mocked_redis_client.decrement_hash_value(key, value, -1)
    mocked_redis_client.redis_store.hincrby.assert_called_with(key, value, -1)


def test_incr_hash_value_should_increment_value_by_one_for_key(mocked_redis_client):
    key = '12345'
    value = "template-1111"

    mocked_redis_client.increment_hash_value(key, value)
    mocked_redis_client.redis_store.hincrby.assert_called_with(key, value, 1)


def test_get_all_from_hash_returns_hash_for_key(mocked_redis_client):
    key = '12345'
    assert mocked_redis_client.get_all_from_hash(key) == {b'template-1111': b'8', b'template-2222': b'8'}
    mocked_redis_client.redis_store.hgetall.assert_called_with(key)


def test_set_hash_and_expire(mocked_redis_client):
    key = 'hash-key'
    values = {'key': 10}
    mocked_redis_client.set_hash_and_expire(key, values, 1)
    mocked_redis_client.redis_store.hmset.assert_called_with(key, values)
    mocked_redis_client.redis_store.expire.assert_called_with(key, 1)


def test_set_hash_and_expire_converts_values_to_valid_types(mocked_redis_client):
    key = 'hash-key'
    values = {uuid.UUID(int=0): 10}
    mocked_redis_client.set_hash_and_expire(key, values, 1)
    mocked_redis_client.redis_store.hmset.assert_called_with(key, {'00000000-0000-0000-0000-000000000000': 10})
    mocked_redis_client.redis_store.expire.assert_called_with(key, 1)


@freeze_time("2001-01-01 12:00:00.000000")
def test_should_add_correct_calls_to_the_pipe(mocked_redis_client, mocked_redis_pipeline):
    mocked_redis_client.exceeded_rate_limit("key", 100, 100)
    assert mocked_redis_client.redis_store.pipeline.called
    mocked_redis_pipeline.zadd.assert_called_with("key", {978350400.0: 978350400.0})
    mocked_redis_pipeline.zremrangebyscore.assert_called_with("key", '-inf', 978350300.0)
    mocked_redis_pipeline.zcard.assert_called_with("key")
    mocked_redis_pipeline.expire.assert_called_with("key", 100)
    assert mocked_redis_pipeline.execute.called


@freeze_time("2001-01-01 12:00:00.000000")
def test_should_fail_request_if_over_limit(mocked_redis_client, mocked_redis_pipeline):
    mocked_redis_pipeline.execute.return_value = [True, True, 100, True]
    assert mocked_redis_client.exceeded_rate_limit("key", 99, 100)


@freeze_time("2001-01-01 12:00:00.000000")
def test_should_allow_request_if_not_over_limit(mocked_redis_client, mocked_redis_pipeline):
    mocked_redis_pipeline.execute.return_value = [True, True, 100, True]
    assert not mocked_redis_client.exceeded_rate_limit("key", 101, 100)


@freeze_time("2001-01-01 12:00:00.000000")
def test_rate_limit_not_exceeded(mocked_redis_client, mocked_redis_pipeline):
    mocked_redis_pipeline.execute.return_value = [True, True, 80, True]
    assert not mocked_redis_client.exceeded_rate_limit("key", 90, 100)


def test_should_not_call_rate_limit_if_not_enabled(mocked_redis_client, mocked_redis_pipeline):
    mocked_redis_client.active = False

    assert not mocked_redis_client.exceeded_rate_limit('key', 100, 100)
    assert not mocked_redis_client.redis_store.pipeline.called


def test_expire(mocked_redis_client):
    key = 'hash-key'
    mocked_redis_client.expire(key, 1)
    mocked_redis_client.redis_store.expire.assert_called_with(key, 1)


def test_delete(mocked_redis_client):
    key = 'hash-key'
    mocked_redis_client.delete(key)
    mocked_redis_client.redis_store.delete.assert_called_with(key)


def test_multi_delete(mocked_redis_client):
    mocked_redis_client.delete('a', 'b', 'c')
    mocked_redis_client.redis_store.delete.assert_called_with('a', 'b', 'c')


@pytest.mark.parametrize('input,output', [
    (b'asdf', b'asdf'),
    ('asdf', 'asdf'),
    (0, 0),
    (1.2, 1.2),
    (uuid.UUID(int=0), '00000000-0000-0000-0000-000000000000'),
    pytest.param({'a': 1}, None, marks=pytest.mark.xfail(raises=ValueError)),
    pytest.param(datetime.utcnow(), None, marks=pytest.mark.xfail(raises=ValueError)),
])
def test_prepare_value(input, output):
    assert prepare_value(input) == output


def test_delete_cache_keys(mocked_redis_client):
    delete_mock = Mock(return_value=4)
    mocked_redis_client.scripts = {'delete-keys-by-pattern': delete_mock}

    ret = mocked_redis_client.delete_cache_keys_by_pattern('foo')

    assert ret == 4
    delete_mock.assert_called_once_with(args=['foo'])


def test_delete_cache_keys_returns_zero_when_redis_disabled(mocked_redis_client):
    mocked_redis_client.active = False
    delete_mock = Mock()
    mocked_redis_client.scripts = {'delete-keys-by-pattern': delete_mock}

    ret = mocked_redis_client.delete_cache_keys_by_pattern('foo')

    assert delete_mock.called is False
    assert ret == 0
