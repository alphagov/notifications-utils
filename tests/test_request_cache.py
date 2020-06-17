import pytest

from notifications_utils.clients.redis import RequestCache
from notifications_utils.clients.redis.redis_client import RedisClient


@pytest.fixture(scope='function')
def mocked_redis_client(app):
    app.config['REDIS_ENABLED'] = True
    redis_client = RedisClient()
    redis_client.init_app(app)
    return redis_client


@pytest.mark.parametrize('args, kwargs, expected_cache_key', (
    (
        [1, 2, 3], {}, '1-2-3-None-None-None'
    ),
    (
        [1, 2, 3, 4, 5, 6], {}, '1-2-3-4-5-6'
    ),
    (
        [1, 2, 3], {'x': 4, 'y': 5, 'z': 6}, '1-2-3-4-5-6'
    ),
    (
        [1, 2, 3, 4], {'y': 5}, '1-2-3-4-5-None'
    ),
))
def test_sets_cache(
    mocker,
    mocked_redis_client,
    args,
    kwargs,
    expected_cache_key,
):
    cache = RequestCache(mocked_redis_client)
    mock_redis_set = mocker.patch.object(
        mocked_redis_client, 'set',
    )
    mock_redis_get = mocker.patch.object(
        mocked_redis_client, 'get',
        return_value=None,
    )

    @cache.set('{a}-{b}-{c}-{x}-{y}-{z}')
    def foo(a, b, c, x=None, y=None, z=None):
        return 'bar'

    assert foo(*args, **kwargs) == 'bar'

    mock_redis_get.assert_called_once_with(expected_cache_key)

    mock_redis_set.assert_called_once_with(
        expected_cache_key,
        '"bar"',
        ex=604_800,
    )


def test_raises_if_key_doesnt_match_arguments(mocked_redis_client):

    cache = RequestCache(mocked_redis_client)

    @cache.set('{baz}')
    def foo(bar):
        pass

    with pytest.raises(KeyError):
        foo(1)

    with pytest.raises(KeyError):
        foo()


def test_gets_from_cache(mocker, mocked_redis_client):

    cache = RequestCache(mocked_redis_client)

    mock_redis_get = mocker.patch.object(
        mocked_redis_client, 'get',
        return_value=b'"bar"',
    )

    @cache.set('{a}-{b}-{c}')
    def foo(a, b, c):
        # This function should not be called because the cache has
        # returned a value
        raise RuntimeError

    assert foo(1, 2, 3) == 'bar'

    mock_redis_get.assert_called_once_with('1-2-3')


def test_deletes_from_cache(mocker, mocked_redis_client):

    cache = RequestCache(mocked_redis_client)

    mock_redis_delete = mocker.patch.object(
        mocked_redis_client, 'delete',
    )

    @cache.delete('{a}-{b}-{c}')
    def foo(a, b, c):
        return 'bar'

    assert foo(1, 2, 3) == 'bar'

    mock_redis_delete.assert_called_once_with('1-2-3')


def test_deletes_from_cache_even_if_call_raises(mocker, mocked_redis_client):

    cache = RequestCache(mocked_redis_client)

    mock_redis_delete = mocker.patch.object(
        mocked_redis_client, 'delete',
    )

    @cache.delete('bar')
    def foo():
        raise RuntimeError

    with pytest.raises(RuntimeError):
        foo()

    mock_redis_delete.assert_called_once_with('bar')
