import numbers
import uuid
from time import time
from types import TracebackType

# (`Type` is deprecated in favour of `type` but we need to match the
# signature of the method we are stubbing)
from typing import (  # noqa: UP035
    Type,
    final,
)

from flask import current_app
from flask_redis import FlaskRedis
from redis.lock import Lock
from redis.typing import Number

from notifications_utils.eventlet import EventletTimeout


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


# a sentinel argument, defined as a class so we can make typing happy
@final
class INSTANCE_DEFAULT:
    pass


class RedisClient:
    redis_store = FlaskRedis()
    active = False
    scripts = {}
    always_raise: tuple[type[BaseException], ...] = (EventletTimeout,)

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
        # checks whether a token-bucket-based rate-limiter has currently
        # exceeded its rate limit, deducting 1 from the token-bucket in
        # the process of doing so (down to a limit of bucket_min). the
        # bucket is replenished at a rate determined by replenish_per_sec
        # up to a maximum of bucket_max. returns the number of tokens
        # remaining in the bucket following replenishment and deductions.
        # if the return value is positive, this indicates that the bucket
        # is not depleted and the request should be served. if bucket_min
        # is negative, the return value can also be negative - this can
        # be used to cause further (denied) requests beyond the rate limit
        # to also count against the limit, but only to a reasonable (and
        # controllable) degree. in this case, negative return values
        # indicate a depleted bucket and the request should not be served.
        #
        # `now` argument is expected to be a locally-sourced float unix
        # epoch UTC timestamp. clock skew between clients shouldn't cause
        # too much weirdness because we only ever allow last_replenished
        # to go forwards - it would just result in slightly "burstier"
        # replenishment than otherwise as most of the replenishment would
        # end up being done by the instances with the most-ahead clock.
        #
        # float arithmetic used for token calculation here is not ideal
        # but shouldn't cause precision problems this century with
        # reasonable rate values. if it did become a problem, this could
        # be trivially modified to only allow replenishment in batches of
        # N tokens (through a divide before and multiply after the floor
        # call)
        self.scripts["tally-bucket-rate-limit"] = self.redis_store.register_script(
            """
            local key = ARGV[1]
            local now = ARGV[2]
            local replenish_per_sec = ARGV[3]
            local bucket_max = ARGV[4]
            local bucket_min = ARGV[5]

            local last_replenished, tokens_remaining
            local value = redis.call('get', key)
            if value == false or string.len(value) < 12 then
                last_replenished = now
                tokens_remaining = bucket_max
            else
                last_replenished, tokens_remaining = struct.unpack('di4', value)
            end

            local elapsed = math.max(now - last_replenished, 0)
            local replenishment = math.floor(elapsed * replenish_per_sec)
            tokens_remaining = math.min(tokens_remaining + replenishment, bucket_max)
            tokens_remaining = math.max(tokens_remaining - 1, bucket_min)
            -- critically, we do not use `now` for our new value of
            -- last_replenished, but the timestamp made-up to the
            -- last whole token we were able to grant in this
            -- iteration. this avoids incorrect behaviour due to
            -- rounding.
            last_replenished = last_replenished + (replenishment / replenish_per_sec)

            value = struct.pack('di4', last_replenished, tokens_remaining)
            redis.call('set', key, value)

            return tokens_remaining
            """
        )

    def get_remaining_bucket_tokens(
        self, key, replenish_per_sec, bucket_max, bucket_min, raise_exception=False, always_raise=INSTANCE_DEFAULT
    ):
        if self.active:
            try:
                now = time()
                return self.scripts["tally-bucket-rate-limit"](
                    args=[key, now, replenish_per_sec, bucket_max, bucket_min]
                )
            except Exception as e:
                self.__handle_exception(e, raise_exception, always_raise, "tally-bucket-rate-limit", key)

    def delete_by_pattern(self, pattern, raise_exception=False, always_raise=INSTANCE_DEFAULT):
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
                self.__handle_exception(e, raise_exception, always_raise, "delete-by-pattern", pattern)

        return 0

    def exceeded_rate_limit(self, cache_key, limit, interval, raise_exception=False, always_raise=INSTANCE_DEFAULT):
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
                self.__handle_exception(e, raise_exception, always_raise, "rate-limit-pipeline", cache_key)
                return False
        else:
            return False

    def set(
        self, key, value, ex=None, px=None, nx=False, xx=False, raise_exception=False, always_raise=INSTANCE_DEFAULT
    ):
        key = prepare_value(key)
        value = prepare_value(value)
        if self.active:
            try:
                self.redis_store.set(key, value, ex, px, nx, xx)
            except Exception as e:
                self.__handle_exception(e, raise_exception, always_raise, "set", key)

    def incr(self, key, raise_exception=False, always_raise=INSTANCE_DEFAULT):
        key = prepare_value(key)
        if self.active:
            try:
                return self.redis_store.incr(key)
            except Exception as e:
                self.__handle_exception(e, raise_exception, always_raise, "incr", key)

    def decrby(self, key, amount, raise_exception=False, always_raise=INSTANCE_DEFAULT):
        if self.active:
            try:
                return self.redis_store.decrby(key, amount)
            except Exception as e:
                self.__handle_exception(e, raise_exception, always_raise, "decrby", key)

    def get(self, key, raise_exception=False, always_raise=INSTANCE_DEFAULT):
        key = prepare_value(key)
        if self.active:
            try:
                return self.redis_store.get(key)
            except Exception as e:
                self.__handle_exception(e, raise_exception, always_raise, "get", key)

        return None

    def delete(self, *keys, raise_exception=False, always_raise=INSTANCE_DEFAULT):
        keys = [prepare_value(k) for k in keys]
        if self.active:
            try:
                self.redis_store.delete(*keys)
            except Exception as e:
                self.__handle_exception(e, raise_exception, always_raise, "delete", ", ".join(keys))

    def get_lock(self, key_name, **kwargs):
        if self.active:
            return Lock(self.redis_store, key_name, **kwargs)
        else:
            return StubLock(redis=None, name="")

    def __handle_exception(
        self,
        e: BaseException,
        raise_exception: bool,
        always_raise: tuple[type[BaseException], ...] | type[INSTANCE_DEFAULT],
        operation: str,
        key_name,
    ) -> None:
        current_app.logger.exception(
            "Redis error performing %s on %s",
            operation,
            key_name,
            extra={"redis_operation": operation, "redis_key": key_name},
        )
        if always_raise is INSTANCE_DEFAULT:
            always_raise = self.always_raise
        if raise_exception or isinstance(e, always_raise or ()):
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
