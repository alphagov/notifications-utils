from collections.abc import Iterator, Mapping, Sequence
from json import JSONEncoder
from typing import Any, Protocol

from flask.json.provider import DefaultJSONProvider as flask_DefaultJSONProvider

type RelaxedJsonType = None | bool | int | float | str | Sequence["RelaxedJsonType"] | Mapping[str, "RelaxedJsonType"]


type StrictJsonType = (
    None
    | bool
    | int
    | float
    | str
    | list["StrictJsonType"]
    | tuple["StrictJsonType", ...]
    | dict[str, "StrictJsonType"]
)


class JSONNormalizingProtocol(Protocol):
    """
    A class that uses a `default` method to normalize a python object into an easily
    JSON-serializable type, e.g. JSONEncoder or flask DefaultJSONProvider
    """

    def default(self, obj: Any) -> StrictJsonType:
        raise NotImplementedError


class RelaxedContainerJSONEncodingMixin:
    """
    Can be mixed in with any JSONNormalizingProtocol class to make it turn (almost) any
    encountered Sequence into a tuple and any Mapping into a plain dict.
    """

    def default(self: JSONNormalizingProtocol, obj: RelaxedJsonType) -> StrictJsonType:
        match obj:
            case bool() | int() | float() | str() | None:
                return obj
            case Sequence() if not isinstance(obj, bytes):
                # not str because those have already been handled
                return tuple(self.default(inner) for inner in obj)
            case Mapping():
                return {k: self.default(v) for k, v in obj.items()}

        return super().default(obj)  # type: ignore[safe-super]


class RelaxedContainerJSONEncoder(RelaxedContainerJSONEncodingMixin, JSONEncoder):
    def encode(self, obj: RelaxedJsonType) -> str:
        return super().encode(obj)

    def iterencode(self, obj: RelaxedJsonType, _one_shot: bool = False) -> Iterator[str]:
        return super().iterencode(obj, _one_shot)


class FlaskRelaxedContainerJSONProvider(RelaxedContainerJSONEncodingMixin, flask_DefaultJSONProvider):
    pass
