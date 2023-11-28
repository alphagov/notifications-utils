from functools import lru_cache
import re
from types import MappingProxyType
from typing.re import Pattern


class RestrictedAny:
    """
    Analogous to mock.ANY, this class takes an arbitrary callable in its constructor and the returned instance will
    appear to "equal" anything that produces a truthy result when passed as an argument to the ``condition`` callable.

    Useful when wanting to assert the contents of a larger structure but be more flexible for certain members, e.g.

    # only care that second number is odd
    >>> (4, 5, 6,) == (4, RestrictedAny(lambda x: x % 2), 6,)
    True
    >>> (4, 9, 6,) == (4, RestrictedAny(lambda x: x % 2), 6,)
    True
    """
    def __init__(self, condition):
        self._condition = condition

    def __eq__(self, other):
        return self._condition(other)

    def __repr__(self):
        return f"{self.__class__.__name__}({self._condition})"

    def __hash__(self):
        return None


class AnySupersetOf(RestrictedAny):
    """
    Instance will appear to "equal" any dictionary-like object that is a "superset" of the the constructor-supplied
    ``subset_dict``, i.e. will ignore any keys present in the dictionary in question but missing from the reference
    dict. e.g.

    >>> [{"a": 123, "b": 456, "less": "predictabananas"}, 789] == [AnySupersetOf({"a": 123, "b": 456}), 789]
    True
    """
    def __init__(self, subset_dict):
        # take an immutable dict copy of supplied dict-like object
        self._subset_dict = MappingProxyType(dict(subset_dict))
        super().__init__(lambda other: self._subset_dict == {k: v for k, v in other.items() if k in self._subset_dict})

    def __repr__(self):
        return f"{self.__class__.__name__}({self._subset_dict})"


class AnyStringMatching(RestrictedAny):
    """
    Instance will appear to "equal" any string that matches the constructor-supplied regex pattern

    >>> {"a": "Metempsychosis", "b": "c"} == {"a": AnyStringMatching(r"m+.+psycho.*", flags=re.I), "b": "c"}
    True
    """
    _cached_re_compile = staticmethod(lru_cache(maxsize=32)(re.compile))

    def __init__(self, *args, **kwargs):
        """
        Construct an instance which will equal any string matching the supplied regex pattern. Supports all arguments
        recognized by ``re.compile``, alternatively accepts an existing regex pattern object as a single argument.
        """
        self._regex = (
            args[0]
            if len(args) == 1 and isinstance(args[0], Pattern)
            else self._cached_re_compile(*args, **kwargs)
        )
        super().__init__(lambda other: isinstance(other, (str, bytes)) and bool(self._regex.match(other)))

    def __repr__(self):
        return f"{self.__class__.__name__}({self._regex})"


class ExactIdentity(RestrictedAny):
    """
    Instance will appear to "equal" only to the exact object supplied at construction time.

    >>> x = []
    >>> (7, ExactIdentity(x),) == (7, x,)
    True
    >>> (7, ExactIdentity(x),) == (7, [],)
    False
    """
    def __init__(self, reference_object):
        self._reference_object = reference_object
        super().__init__(lambda other: self._reference_object is other)

    def __repr__(self):
        return f"{self.__class__.__name__}({self._reference_object!r} @ {hex(id(self._reference_object))})"
