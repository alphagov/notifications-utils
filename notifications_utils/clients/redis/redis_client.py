import numbers
import uuid
from time import time
from types import TracebackType

# (`Type` is deprecated in favour of `type` but we need to match the
# signature of the method we are stubbing)
from typing import Type  # noqa: UP035

from flask import current_app
from flask_redis import FlaskRedis
from redis.lock import Lock
from redis.typing import Number


def prepare_value(val):
    """
    Only bytes, strings and numbers (ints, longs and floats) are acceptable
    for keys and values. Previously redis-py attempted to cast other types
    to str() and store the result. This caused must confusion and frustration
    when passing boolean values (cast to 'True' and 'False') or None values
    (cast to 'None'). It is now the user's responsibility to cast all
    key names and values to bytes, strings or numbers before passing the
    value to redis-py.
    """
    # things redis-py natively supports
    if isinstance(
        val,
        bytes | str | numbers.Number,
    ):
        return val
    # things we know we can safely cast to string
    elif isinstance(val, uuid.UUID):
        return str(val)
    else:
        raise ValueError(f"cannot cast {type(val)} to a string")


class RedisClient:
    redis_store = FlaskRedis()
    active = False
    scripts = {}

    def init_app(self, app):
        self.active = app.config.get("REDIS_ENABLED")
        if self.active:
            self.redis_store.init_app(app)

            self.register_scripts()

    def register_scripts(self):
        # delete keys matching a pattern supplied as a parameter. Does so in batches of 5000 to prevent unpack from
        # exceeding lua's stack limit, and also to prevent errors if no keys match the pattern.
        # Inspired by https://gist.github.com/ddre54/0a4751676272e0da8186
        self.scripts["delete-keys-by-pattern"] = self.redis_store.register_script(
            """
            local keys = redis.call('keys', ARGV[1])
            local deleted = 0
            for i=1, #keys, 5000 do
                deleted = deleted + redis.call('del', unpack(keys, i, math.min(i + 4999, #keys)))
            end
            return deleted
            """
        )
        self.scripts["overwrite-keys-by-pattern"] = self.redis_store.register_script(
            """
            local pattern = ARGV[1]
            local new_value = ARGV[2]

            local keys = redis.call('keys', pattern)
            local overwritten = 0
            for i=1, #keys, 2500 do
                local mset_args = {}
                for j=i, math.min(i + 2499, #keys) do
                    table.insert(mset_args, keys[j])
                    table.insert(mset_args, new_value)
                end

                redis.call('mset', unpack(mset_args))
                overwritten = overwritten + #mset_args/2
            end
            return overwritten
            """
        )
        self.scripts["set-if-timestamp-newer"] = self.redis_store.register_script(
            """
            local key = ARGV[1]
            local new_value = ARGV[2]
            local ttl = ARGV[3]

            local existing_value = redis.call('get', key)
            if existing_value then
                -- if unpacking the new value fails or we can't find a timestamp in it, we
                -- probably want to let this throw an error - calling this script with an
                -- inappropriate payload is Wrong.
                local unpacked_new_value = cmsgpack.unpack(new_value)

                -- if unpacking the existing value fails or we can't find a timestamp
                -- key in it, we'll just fall through and overwrite it like normal set would
                local success, unpacked_existing_value = pcall(cmsgpack.unpack, existing_value)
                if success and type(unpacked_existing_value) == 'table' and unpacked_existing_value['timestamp'] then
                    if unpacked_existing_value['timestamp'] > unpacked_new_value['timestamp'] then
                        -- existing value is "newer" according to the timestamp, so don't replace
                        return false
                    end
                end
            end

            local maybe_ex_args = {}
            if ttl then
                maybe_ex_args = {'ex', ttl}
            end
            redis.call('set', key, new_value, unpack(maybe_ex_args))

            return true
            """
        )

    def overwrite_by_pattern(self, pattern, value, raise_exception=False):
        """
        similar to `delete_by_pattern`, will overwrite all keys matching `pattern` with
        `value`
        """
        if self.active:
            try:
                return self.scripts["overwrite-keys-by-pattern"](args=[pattern, value])
            except Exception as e:
                self.__handle_exception(e, raise_exception, "overwrite-by-pattern", pattern)

        return 0

    def delete_by_pattern(self, pattern, raise_exception=False):
        r"""
        Deletes all keys matching a given pattern, and returns how many keys were deleted.
        Pattern is defined as in the KEYS command: https://redis.io/commands/keys

        * h?llo matches hello, hallo and hxllo
        * h*llo matches hllo and heeeello
        * h[ae]llo matches hello and hallo, but not hillo
        * h[^e]llo matches hallo, hbllo, ... but not hello
        * h[a-b]llo matches hallo and hbllo

        Use \ to escape special characters if you want to match them verbatim
        """
        if self.active:
            try:
                return self.scripts["delete-keys-by-pattern"](args=[pattern])
            except Exception as e:
                self.__handle_exception(e, raise_exception, "delete-by-pattern", pattern)

        return 0

    def exceeded_rate_limit(self, cache_key, limit, interval, raise_exception=False):
        """
        Rate limiting.
        - Uses Redis sorted sets
        - Also uses redis "multi" which is abstracted into pipeline() by FlaskRedis/PyRedis
        - Sends all commands to redis as a group to be executed atomically

        Method:
        (1) Add event, scored by timestamp (zadd). The score determines order in set.
        (2) Use zremrangebyscore to delete all set members with a score between
            - Earliest entry (lowest score == earliest timestamp) - represented as '-inf'
                and
            - Current timestamp minus the interval
            - Leaves only relevant entries in the set (those between now and now - interval)
        (3) Count the set
        (4) If count > limit fail request
        (5) Ensure we expire the set key to preserve space

        Notes:
        - Failed requests count. If over the limit and keep making requests you'll stay over the limit.
        - The actual value in the set is just the timestamp, the same as the score. We don't store any requets details.
        - return value of pipe.execute() is an array containing the outcome of each call.
            - result[2] == outcome of pipe.zcard()
        - If redis is inactive, or we get an exception, allow the request

        :param cache_key:
        :param limit: Number of requests permitted within interval
        :param interval: Interval we measure requests in
        :param raise_exception: Should throw exception
        :return:
        """
        cache_key = prepare_value(cache_key)
        if self.active:
            try:
                pipe = self.redis_store.pipeline()
                when = time()
                pipe.zadd(cache_key, {when: when})
                pipe.zremrangebyscore(cache_key, "-inf", when - interval)
                pipe.zcard(cache_key)
                pipe.expire(cache_key, interval)
                result = pipe.execute()
                return result[2] > limit
            except Exception as e:
                self.__handle_exception(e, raise_exception, "rate-limit-pipeline", cache_key)
                return False
        else:
            return False

    def set_if_timestamp_newer(self, key, value, ex=None, raise_exception=False):
        """
        Expects `value` to be a bytestring containing a msgpack-encoded dict
        with a `timestamp` toplevel key containing a float unix timestamp.

        If existing redis contents are also a msgpack-encoded dict containing
        a `timestamp` toplevel key, these two (float) timestamps are compared
        and the new value is only set if its timestamp is the higher of the
        two.

        If a timestamp can't be found in the existing value, the new value
        is set unconditionally.

        The other contents of the msgpack-encoded dict can be arbitrary.

        Returns a boolean signifying whether the new value was set.
        """
        if self.active:
            try:
                return self.scripts["set-if-timestamp-newer"](args=[key, value, ex], keys=[key])
            except Exception as e:
                self.__handle_exception(e, raise_exception, "set-if-timestamp-newer", key)

        return False

    def set(self, key, value, ex=None, px=None, nx=False, xx=False, raise_exception=False):
        key = prepare_value(key)
        value = prepare_value(value)
        if self.active:
            try:
                self.redis_store.set(key, value, ex, px, nx, xx)
            except Exception as e:
                self.__handle_exception(e, raise_exception, "set", key)

    def incr(self, key, raise_exception=False):
        key = prepare_value(key)
        if self.active:
            try:
                return self.redis_store.incr(key)
            except Exception as e:
                self.__handle_exception(e, raise_exception, "incr", key)

    def decrby(self, key, amount, raise_exception=False):
        if self.active:
            try:
                return self.redis_store.decrby(key, amount)
            except Exception as e:
                self.__handle_exception(e, raise_exception, "decrby", key)

    def get(self, key, raise_exception=False):
        key = prepare_value(key)
        if self.active:
            try:
                return self.redis_store.get(key)
            except Exception as e:
                self.__handle_exception(e, raise_exception, "get", key)

        return None

    def delete(self, *keys, raise_exception=False):
        keys = [prepare_value(k) for k in keys]
        if self.active:
            try:
                self.redis_store.delete(*keys)
            except Exception as e:
                self.__handle_exception(e, raise_exception, "delete", ", ".join(keys))

    def get_lock(self, key_name, **kwargs):
        if self.active:
            return Lock(self.redis_store, key_name, **kwargs)
        else:
            return StubLock(redis=None, name="")

    def __handle_exception(self, e, raise_exception, operation, key_name):
        current_app.logger.exception("Redis error performing %s on %s", operation, key_name)
        if raise_exception:
            raise e


class StubLock:
    def __init__(
        self,
        redis,
        name: str,
        timeout: Number | None = None,
        sleep: Number = 0.1,
        blocking: bool = True,
        blocking_timeout: Number | None = None,
        thread_local: bool = True,
    ):
        self._locked = False
        return None

    def __enter__(self) -> "StubLock":
        self._locked = True
        return self

    def __exit__(
        self,
        exc_type: Type[BaseException] | None,  # noqa: UP006
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._locked = False

    def acquire(
        self,
        sleep: Number | None = None,
        blocking: bool | None = None,
        blocking_timeout: Number | None = None,
        token: str | None = None,
    ) -> bool:
        self._locked = True
        return True

    def extend(self, additional_time: int, replace_ttl: bool = False) -> bool:
        return True

    def locked(self) -> bool:
        return self._locked

    def owned(self) -> bool:
        return self._locked

    def release(self) -> None:
        self._locked = False

    def reacquire(self) -> bool:
        self._locked = True
        return True
