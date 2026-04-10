from functools import lru_cache

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
    @lru_cache(maxsize=1_234, typed=False)  # Should match 1000 cols * number of workers
    def make_key(original_key):
        if original_key is None:
            return None
        return original_key.translate(InsensitiveDict.KEY_TRANSLATION_TABLE).lower()


class InsensitiveSet(OrderedSet):
    """
    `InsensitiveSet` behaves like a normal set, except:
    - it is ordered
    - it normalises case, whitespace, hypens and underscores in items

    In other words:
        InsensitiveSet(['FIRST_NAME']) == InsensitiveSet(['first name'])
        >>> True

    Note that the provided case and spacing is preserved for presentation, so:
        InsensitiveSet(['FIRST-name'])[0]
        >>> 'FIRST-name'
    """

    def __init__(self, iterable=None, /):
        return super().__init__(InsensitiveDict.from_keys(iterable or ()).values())

    def __contains__(self, key):
        return key in InsensitiveDict.from_keys(self)

    def __eq__(self, other):
        return not self ^ other

    def __le__(self, other):
        return self.issubset(other)

    def __lt__(self, other):
        return self <= other and not self == other

    def __sub__(self, other):
        return self.difference(other)

    def index(self, key):
        return InsensitiveDict.from_keys(self).keys().index(InsensitiveDict.make_key(key))

    def issubset(self, other):
        return all(key in self.__class__(other) for key in self)

    def intersection(self, other):
        other_as_same_type_as_self = self.__class__(other)
        both = self | other_as_same_type_as_self
        return self.__class__(item for item in both if item in self and item in other_as_same_type_as_self)

    def difference(self, other):
        return self.__class__(item for item in self if item not in self.__class__(other))
