from collections.abc import Callable
from typing import Self


class Take(str):
    def then(self, func: Callable[..., str], *args, **kwargs) -> Self:
        return self.__class__(func(self, *args, **kwargs))
