import json
from contextlib import suppress
from datetime import datetime, timedelta
from functools import wraps
from inspect import signature


def daily_limit_cache_key(service_id):
    return "{}-{}-{}".format(str(service_id), datetime.utcnow().strftime("%Y-%m-%d"), "count")


def rate_limit_cache_key(service_id, api_key_type):
    return "{}-{}".format(str(service_id), api_key_type)


class RequestCache():

    TTL = int(timedelta(days=7).total_seconds())

    def __init__(self, redis_client):
        self.redis_client = redis_client

    @staticmethod
    def _get_argument(argument_name, client_method, args, kwargs):

        with suppress(KeyError):
            return kwargs[argument_name]

        with suppress(ValueError, IndexError):
            argument_index = list(signature(client_method).parameters).index(argument_name)
            return args[argument_index]

        with suppress(KeyError):
            return signature(client_method).parameters[argument_name].default

        raise TypeError("{}() takes no argument called '{}'".format(
            client_method.__name__, argument_name
        ))

    @staticmethod
    def _make_key(key_format, client_method, args, kwargs):
        return key_format.format(**{
            argument_name: RequestCache._get_argument(argument_name, client_method, args, kwargs)
            for argument_name in list(signature(client_method).parameters)
        })

    def set(self, key_format):

        def _set(client_method):

            @wraps(client_method)
            def new_client_method(*args, **kwargs):
                redis_key = RequestCache._make_key(key_format, client_method, args, kwargs)
                cached = self.redis_client.get(redis_key)
                if cached:
                    return json.loads(cached.decode('utf-8'))
                api_response = client_method(*args, **kwargs)
                self.redis_client.set(
                    redis_key,
                    json.dumps(api_response),
                    ex=self.TTL,
                )
                return api_response

            return new_client_method
        return _set

    def delete(self, key_format):

        def _delete(client_method):

            @wraps(client_method)
            def new_client_method(*args, **kwargs):
                try:
                    api_response = client_method(*args, **kwargs)
                finally:
                    redis_key = self._make_key(key_format, client_method, args, kwargs)
                    self.redis_client.delete(redis_key)
                return api_response

            return new_client_method

        return _delete
