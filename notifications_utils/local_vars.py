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
    expected_type: type[T] | None

    def __init__(
        self,
        context_var: ContextVar[T | None],
        factory: Callable[[], T],
        expected_type: type[T] | None = None,
    ):
        """
        Given a reference to a `context_var`, the resulting instance will be a callable that
        returns the current context's contents of that `context_var`, pre-populating it with
        the results of a (zero-argument) call to `factory` if it is empty or None.

        If `expected_type` is specified, the `factory` call's return value is checked to be
        of that type, but in return the `.expected_type` attribute is accessible without
        triggering population.
        """
        self.context_var = context_var
        self.factory = factory
        self.expected_type = expected_type

    def __call__(self) -> T:
        r = self.context_var.get(None)
        if r is None:
            r = self.factory()

            # exact type testing here, none of your issubclass flexibility
            if self.expected_type is not None and type(r) is not self.expected_type:
                raise TypeError(
                    f"factory returned value (of type {type(r)}) that is not of the expected type {self.expected_type}"
                )

            self.context_var.set(r)

        return r

    def clear(self) -> None:
        self.context_var.set(None)
