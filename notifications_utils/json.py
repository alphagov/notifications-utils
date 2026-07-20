from collections.abc import Mapping, Sequence

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


def json_encodable(value: RelaxedJsonType) -> StrictJsonType:
    match value:
        case bool() | int() | float() | str() | None:
            return value
        case Sequence():
            # not str because those have already been handled
            return tuple(json_encodable(inner) for inner in value)
        case Mapping():
            return {k: json_encodable(v) for k, v in value.items()}
        case _:
            raise TypeError(f"Unexpected type {type(value)}")
