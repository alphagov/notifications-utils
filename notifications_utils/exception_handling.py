from contextlib import contextmanager


def _find_and_reraise_exception(
    exc: BaseException | None, target_exceptions: type[BaseException] | tuple[type[BaseException], ...]
):
    if exc is not None:
        if isinstance(exc, target_exceptions):
            raise exc

        _find_and_reraise_exception(exc.__cause__, target_exceptions)
        _find_and_reraise_exception(exc.__context__, target_exceptions)


@contextmanager
def extract_reraise_chained_exception(target_exceptions: type[BaseException] | tuple[type[BaseException], ...]):
    """
    Context manager: if the wrapped block results in an exception, will fish through the chained
    exceptions (through __cause__ and __context__) looking for an exception that matches a type
    in `target_exceptions`. If it finds one it will re-raise it.

    This is useful if upstream code catches an exception that you'd rather it didn't and reinterprets
    it as one of its own exceptions.
    """
    try:
        yield
    except BaseException as exc:
        _find_and_reraise_exception(exc, target_exceptions)
        raise exc
