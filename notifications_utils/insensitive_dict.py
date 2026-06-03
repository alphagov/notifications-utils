from abc import ABCMeta, abstractmethod
from collections.abc import Iterable, Iterator, MutableSet, Sequence, Set
from functools import lru_cache
from itertools import chain, islice
from types import NotImplementedType
from typing import Self, TypeVar, overload

from ordered_set import OrderedSet


class InsensitiveDict(dict):
    """
    `InsensitiveDict` behaves like an ordered dictionary, except it normalises
    case, whitespace, hypens and underscores in keys.

    In other words,
    InsensitiveDict({'FIRST_NAME': 'example'}) == InsensitiveDict({'first name': 'example'})
    >>> True
    """

    KEY_TRANSLATION_TABLE = {ord(c): None for c in " _-"}

    def __init__(self, row_dict, overwrite_duplicates=True):
        for key, value in row_dict.items():
            if overwrite_duplicates or key not in self:
                self[key] = value

    @classmethod
    def from_keys(cls, keys):
        """
        This behaves like `dict.from_keys`, except:
        - it normalises the keys to ignore case, whitespace, hypens and
          underscores
        - it stores the original, unnormalised key as the value of the
          item so it can be retrieved later
        """
        return cls({key: key for key in keys}, overwrite_duplicates=False)

    def keys(self):
        return OrderedSet(super().keys())

    def __getitem__(self, key):
        return super().__getitem__(self.make_key(key))

    def __setitem__(self, key, value):
        super().__setitem__(self.make_key(key), value)

    def __contains__(self, key):
        return super().__contains__(self.make_key(key))

    def get(self, key, default=None):
        return self[key] if key in self else default

    def copy(self):
        return self.__class__(super().copy())

    def as_dict_with_keys(self, keys):
        return {key: self.get(key) for key in keys}

    @staticmethod
    @lru_cache(maxsize=1_024, typed=False)  # Corresponds to 1,000 column limit when reading Excel files
    def make_key(original_key: str) -> str:
        if original_key is None:
            return None
        return original_key.translate(InsensitiveDict.KEY_TRANSLATION_TABLE).lower()


T = TypeVar("T")


class AbstractInsensitiveSet(MutableSet[T], Sequence[T], metaclass=ABCMeta):
    __slots__ = ("_inner",)
    _inner: dict[T, T]

    @staticmethod
    @abstractmethod
    def make_key(original_key: T) -> T:
        return original_key

    def __init__(self, it: Iterable[T] | None = None, /):
        self._inner = {self.make_key(item): item for item in (it or ())}

    @classmethod
    def _from_inner_pairs(cls, inner_pairs: Iterable[tuple[T, T]]) -> Self:
        new_set = cls()
        new_set._inner.update(inner_pairs)
        return new_set

    # Set[T]

    def __contains__(self, item) -> bool:
        return self.make_key(item) in self._inner

    def __iter__(self) -> Iterator[T]:
        return iter(self._inner.values())

    def __len__(self) -> int:
        return len(self._inner)

    # MutableSet[T]

    def add(self, item: T):
        self._inner[self.make_key(item)] = item

    def discard(self, item: T):
        self._inner.pop(
            self.make_key(item), None
        )  # faster than possibly raising then ignoring exception if not present

    # Sequence[T]

    @overload
    def __getitem__(self, index: int) -> T: ...

    @overload
    def __getitem__(self, index: slice) -> Self: ...

    def __getitem__(self, index):  # noqa: C901 is bunk
        length = len(self._inner)

        if isinstance(index, slice):
            start, stop, step = index.start, index.stop, index.step

            if step is None:
                step = 1
            if start is None:
                start = 0 if step > 0 else length
            if stop is None:
                stop = length if step > 0 else -(length + 1)

            if start < 0:
                start += length
            if stop < 0:
                stop += length

            if step < 0:
                it = reversed(self._inner.items())
                start = max(length - (start + 1), 0)
                stop = max(length - (stop + 1), 0)
            else:
                it = iter(self._inner.items())
                start = max(start, 0)
                stop = max(stop, 0)

            return type(self)._from_inner_pairs(islice(it, start, stop, abs(step)))

        elif isinstance(index, int):
            if index < 0:
                index = index + length
                if index < 0:
                    raise IndexError
            elif index >= length:
                raise IndexError

            if index > length // 2:
                # faster to iterate to it backwards
                return next(islice(reversed(self._inner.values()), length - (index + 1), length - index))

            return next(islice(self._inner.values(), index, index + 1))

        else:
            raise TypeError

    # make __eq__ work with Iterables to match OrderedSet behaviour

    def __eq__(self, other) -> bool:
        if not isinstance(other, Iterable):
            return False

        if not isinstance(other, Set):
            return tuple(self._inner.keys()) == tuple(self.make_key(item) for item in other)

        return super().__eq__(other)

    # Accelerate Sequence[T]

    def __reversed__(self) -> Iterator[T]:
        return reversed(self._inner.values())

    def index(self, item: T, start: int | None = 0, stop: int | None = None) -> int:
        key = self.make_key(item)
        for i, candidate in enumerate(islice(self._inner.keys(), start, stop), start or 0):
            if candidate == key:
                return i

        raise KeyError

    # Accelerate Set[T]

    def __le__(self, other: Set) -> bool | NotImplementedType:
        if not isinstance(other, Set):
            return NotImplemented

        other_set = other if type(self) is type(other) else type(self)(other)  # type comparison deliberately strict

        return self._inner.keys() <= other_set._inner.keys()

    def __ge__(self, other: Set) -> bool | NotImplementedType:
        if not isinstance(other, Set):
            return NotImplemented

        other_set = other if type(self) is type(other) else type(self)(other)  # type comparison deliberately strict

        return self._inner.keys() >= other_set._inner.keys()

    def __and__(self, other: Iterable) -> Self | NotImplementedType:
        if not isinstance(other, Iterable):
            return NotImplemented

        other_set = other if type(self) is type(other) else type(self)(other)  # type comparison deliberately strict

        # ensure the un-normalised values come from the RHS
        return type(self)._from_inner_pairs((k, other_set._inner[k]) for k in self._inner if k in other_set._inner)

    def __rand__(self, other: Iterable) -> Self | NotImplementedType:
        if not isinstance(other, Iterable):
            return NotImplemented

        if type(self) is type(other):  # type comparison deliberately strict
            # ensure the un-normalised values come from the RHS
            return type(self)._from_inner_pairs((k, self._inner[k]) for k in other._inner if k in self._inner)

        # ensure the un-normalised values come from the RHS
        return type(self)(self._inner[self.make_key(item)] for item in other if item in self)

    def __or__(self, other: Iterable) -> Self | NotImplementedType:
        if not isinstance(other, Iterable):
            return NotImplemented

        new_set = type(self)._from_inner_pairs(self._inner.items())

        if type(self) is type(other):  # type comparison deliberately strict
            new_set._inner.update(other._inner.items())
        else:
            for value in other:
                new_set.add(value)

        return new_set

    def __ror__(self, other: Iterable) -> Self | NotImplementedType:
        if not isinstance(other, Iterable):
            return NotImplemented

        if type(self) is type(other):  # type comparison deliberately strict
            new_set = type(self)._from_inner_pairs(other._inner.items())
        else:
            new_set = type(self)(other)

        new_set._inner.update(self._inner.items())

        return new_set

    def isdisjoint(self, other: Iterable) -> bool | NotImplementedType:
        if not isinstance(other, Iterable):
            return NotImplemented

        if type(self) is type(other):  # type comparison deliberately strict
            return self._inner.keys().isdisjoint(other._inner.keys())

        return not any(item in self for item in other)

    def __sub__(self, other: Iterable) -> Self | NotImplementedType:
        if not isinstance(other, Iterable):
            return NotImplemented

        other_set = other if type(self) is type(other) else type(self)(other)  # type comparison deliberately strict

        return type(self)._from_inner_pairs((k, v) for k, v in self._inner.items() if k not in other_set._inner)

    def __rsub__(self, other: Iterable) -> Self | NotImplementedType:
        if not isinstance(other, Iterable):
            return NotImplemented

        if type(self) is type(other):  # type comparison deliberately strict
            return type(self)._from_inner_pairs((k, v) for k, v in other._inner.items() if k not in self._inner)

        return type(self)(item for item in other if item not in self)

    def __xor__(self, other: Iterable) -> Self | NotImplementedType:
        if not isinstance(other, Iterable):
            return NotImplemented

        other_set = other if type(self) is type(other) else type(self)(other)  # type comparison deliberately strict

        return type(self)._from_inner_pairs(
            chain(
                ((k, v) for k, v in self._inner.items() if k not in other_set._inner),
                ((k, v) for k, v in other_set._inner.items() if k not in self._inner),
            )
        )

    def __rxor__(self, other: Iterable) -> Self | NotImplementedType:
        if not isinstance(other, Iterable):
            return NotImplemented

        other_set = other if type(self) is type(other) else type(self)(other)  # type comparison deliberately strict

        return type(self)._from_inner_pairs(
            chain(
                ((k, v) for k, v in other_set._inner.items() if k not in self._inner),
                ((k, v) for k, v in self._inner.items() if k not in other_set._inner),
            )
        )

    # Accelerate MutableSet[T]

    def remove(self, item: T):
        del self._inner[self.make_key(item)]

    def pop(self):
        try:
            return self._inner.pop(next(reversed(self._inner)))
        except StopIteration as e:
            raise KeyError from e

    def clear(self):
        self._inner.clear()

    def __iand__(self, other: Iterable) -> Self | NotImplementedType:
        if not isinstance(other, Iterable):
            return NotImplemented

        other_set = other if type(self) is type(other) else type(self)(other)  # type comparison deliberately strict

        for k in tuple(self._inner):  # must take copy of keys so we can modify underlying dict during iteration
            if k in other_set._inner:
                # ensure the un-normalised values come from the RHS
                self._inner[k] = other_set._inner[k]
            else:
                del self._inner[k]

        return self

    def __ixor__(self, other: Iterable) -> Self | NotImplementedType:
        if not isinstance(other, Iterable):
            return NotImplemented

        other_set = other if type(self) is type(other) else type(self)(other)  # type comparison deliberately strict

        intersection = self & other_set
        self -= intersection
        other_set -= intersection
        self |= other_set

        return self

    def __isub__(self, other: Iterable) -> Self | NotImplementedType:
        if not isinstance(other, Iterable):
            return NotImplemented

        if type(self) is type(other):  # type comparison deliberately strict
            for k in other._inner:
                self._inner.pop(k, None)

        return super().__isub__(other)  # type: ignore[arg-type]

    def __ior__(self, other: Iterable) -> Self | NotImplementedType:
        if not isinstance(other, Iterable):
            return NotImplemented

        if type(self) is type(other):  # type comparison deliberately strict
            self._inner.update(other._inner.items())

        return super().__ior__(other)  # type: ignore[arg-type]

    # only included because old InsensitiveSet implemented them (note builtins.set accepts *others)

    def issubset(self, other: Set) -> bool:
        return self <= other

    def issuperset(self, other: Set) -> bool:
        return self >= other

    def intersection(self, other: Iterable) -> Self:
        return self & other

    def difference(self, other: Iterable) -> Self:
        return self - other

    def union(self, other: Iterable) -> Self:
        return self | other

    def symmetric_difference(self, other: Iterable) -> Self:
        return self ^ other

    # generally helpful

    def __str__(self) -> str:
        return f"{self.__class__.__name__}({list(self._inner.values())})"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({list(self._inner.values())!r})"


class InsensitiveSet(AbstractInsensitiveSet[str]):
    @staticmethod
    def make_key(original_key: str) -> str:
        return InsensitiveDict.make_key(original_key)
