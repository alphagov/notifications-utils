from collections.abc import Callable
from contextvars import ContextVar
from typing import Generic, TypeVar

T = TypeVar("T")


class LazyLocalGetter(Generic[T]):
    """
    Wrapper for lazily-constructed context-local resources
    """

    context_var: ContextVar[T | None]
    factory: Callable[[], T]

    def __init__(self, context_var: ContextVar[T | None], factory: Callable[[], T]):
        """
        Given a reference to a `context_var`, the resulting instance will be a callable that
        returns the current context's contents of that `context_var`, pre-populating it with
        the results of a (zero-argument) call to `factory` if it is empty or None
        """
        self.context_var = context_var
        self.factory = factory

    def __call__(self) -> T:
        r = self.context_var.get(None)
        if r is None:
            r = self.factory()
            self.context_var.set(r)

        return r

    def clear(self) -> None:
        self.context_var.set(None)
