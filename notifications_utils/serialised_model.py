from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any

from notifications_utils.timezones import utc_string_to_aware_gmt_datetime


class SerialisedModel:
    """
    A SerialisedModel takes a dictionary, typically created by
    serialising a database object. It then takes the value of specified
    keys from the dictionary and adds them to itself as properties, so
    that it can be interacted with like any other object. It is cleaner
    and safer than dealing with dictionaries directly because it
    guarantees that:
    - all of the fields in its annotations are present in the underlying
      dictionary
    - any other abritrary properties of the underlying dictionary can’t
      be accessed

    If you are adding a new field to a model, you should ensure that
    all sources of the cache data are updated to return that new field,
    then clear the cache, before adding that field to the class’s
    annotations.
    """

    def __new__(cls, *args, **kwargs):
        for parent in cls.__mro__:
            cls.__annotations__ = getattr(parent, "__annotations__", {}) | cls.__annotations__
        return super().__new__(cls)

    def __init__(self, _dict):
        for property, type_ in self.__annotations__.items():
            value = self.coerce_value_to_type(_dict[property], type_)
            setattr(self, property, value)

    @staticmethod
    def coerce_value_to_type(value, type_):
        if type_ is Any or value is None:
            return value

        if issubclass(type_, datetime):
            return utc_string_to_aware_gmt_datetime(value).astimezone(UTC)

        return type_(value)


class SerialisedModelCollection(ABC):
    """
    A SerialisedModelCollection takes a list of dictionaries, typically
    created by serialising database objects. When iterated over it
    returns a model instance for each of the items in the list.
    """

    @property
    @abstractmethod
    def model(self):
        pass

    def __init__(self, items):
        self.items = items

    def __bool__(self):
        return bool(self.items)

    def __getitem__(self, index):
        return self.model(self.items[index])

    def __len__(self):
        return len(self.items)

    def __add__(self, other):
        return list(self) + list(other)

    def __radd__(self, other):
        return list(other) + list(self)
