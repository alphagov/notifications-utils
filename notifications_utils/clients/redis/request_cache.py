import json
from contextlib import suppress
from dataclasses import dataclass
from datetime import timedelta
from functools import singledispatch, wraps
from inspect import signature
from typing import TypeAlias
from uuid import UUID

_JSON: TypeAlias = dict[str, "_JSON"] | list["_JSON"] | str | int | float | bool | None


class RequestCache:
    DEFAULT_TTL = int(timedelta(days=28).total_seconds())

    @dataclass
    class CacheResultWrapper:
        """
        Allows the result returned from a `RequestCache.set`-wrapped function to
        be annotated with a dynamically-determined "decision" on whether this result
        should be cached or not (and for how long).

        The truthiness of `cache_decision` controls whether a result will be cached.

        Setting `ttl_in_seconds_override` to its default `None` will result in the
        `ttl_in_seconds` value specified at decoration-time being used.

        Either way, the `value` is extracted by the `RequestCache.set` decorator and
        the `CacheResultWrapper` is discarded before returning the value on its own
        (and possibly caching the value).
        """

        value: _JSON
        cache_decision: bool
        ttl_in_seconds_override: int | None = None

    def __init__(self, redis_client):
        self.redis_client = redis_client

        # get_cache_decision and get_cache_value added to *instance* so that individual
        # instances can have custom implementations `.register`-ed without having a
        # global effect

        def get_cache_decision(result) -> bool:
            return True

        self.get_cache_decision = singledispatch(get_cache_decision)

        def get_ttl_in_seconds_override(result) -> int | None:
            return None

        self.get_ttl_in_seconds_override = singledispatch(get_ttl_in_seconds_override)

        def get_cache_value(result) -> _JSON:
            return result

        self.get_cache_value = singledispatch(get_cache_value)

        @self.get_cache_decision.register
        def _(result: RequestCache.CacheResultWrapper) -> bool:
            return result.cache_decision

        @self.get_ttl_in_seconds_override.register
        def _(result: RequestCache.CacheResultWrapper) -> int | None:
            return result.ttl_in_seconds_override

        @self.get_cache_value.register
        def _(result: RequestCache.CacheResultWrapper) -> _JSON:
            return result.value

    @staticmethod
    def _format_argument(argument):
        if isinstance(argument, str):
            with suppress(ValueError):
                return str(UUID(argument)).lower()
        return argument

    @staticmethod
    def _get_argument(argument_name, client_method, args, kwargs):
        with suppress(KeyError):
            return kwargs[argument_name]

        with suppress(ValueError, IndexError):
            argument_index = list(signature(client_method).parameters).index(argument_name)
            return args[argument_index]

        with suppress(KeyError):
            return signature(client_method).parameters[argument_name].default

        raise TypeError("{client_method.__name__}() takes no argument called '{argument_name}'")

    @staticmethod
    def _make_key(key_format, client_method, args, kwargs):
        return key_format.format(
            **{
                argument_name: RequestCache._format_argument(
                    RequestCache._get_argument(argument_name, client_method, args, kwargs)
                )
                for argument_name in list(signature(client_method).parameters)
            }
        )

    def set(self, key_format, *, ttl_in_seconds=DEFAULT_TTL):
        def _set(client_method):
            @wraps(client_method)
            def new_client_method(*args, **kwargs):
                redis_key = RequestCache._make_key(key_format, client_method, args, kwargs)
                cached = self.redis_client.get(redis_key)
                if cached:
                    return json.loads(cached.decode("utf-8"))

                result = client_method(*args, **kwargs)

                value = self.get_cache_value(result)

                if self.get_cache_decision(result):
                    final_ttl = self.get_ttl_in_seconds_override(result)
                    if final_ttl is None:
                        final_ttl = ttl_in_seconds

                    self.redis_client.set(
                        redis_key,
                        json.dumps(value),
                        ex=int(final_ttl),
                    )

                return value

            return new_client_method

        return _set

    def delete(self, key_format):
        def _delete(client_method):
            @wraps(client_method)
            def new_client_method(*args, **kwargs):
                redis_key = self._make_key(key_format, client_method, args, kwargs)

                # It is important to attempt the redis deletion first and raise an exception
                # if it is unsuccessful. If we didn't, then we risk having a successful API
                # call that updates the database, but redis left with stale data. Stale data
                # is worse then failing the users requests
                self.redis_client.delete(redis_key, raise_exception=True)

                api_response = client_method(*args, **kwargs)

                # We also attempt another redis deletion after the API. This is to deal with
                # the race condition where another request repopulates redis with the old data
                # before the database has been updated. We want to raise an exception if the call
                # to redis here fails because that will hopefully prompt the user that something
                # went wrong and they should retry their action (hopefully resolving the problem).
                self.redis_client.delete(redis_key, raise_exception=True)
                return api_response

            return new_client_method

        return _delete

    def delete_by_pattern(self, key_format):
        def _delete(client_method):
            @wraps(client_method)
            def new_client_method(*args, **kwargs):
                # See equivalent comments above for why we attempt the redis delete before and
                # after the API call
                redis_key = self._make_key(key_format, client_method, args, kwargs)
                self.redis_client.delete_by_pattern(redis_key, raise_exception=True)
                api_response = client_method(*args, **kwargs)
                self.redis_client.delete_by_pattern(redis_key, raise_exception=True)
                return api_response

            return new_client_method

        return _delete
