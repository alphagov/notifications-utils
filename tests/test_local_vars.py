from contextvars import ContextVar
from itertools import count
from unittest import mock

from notifications_utils.local_vars import LazyLocalGetter


def test_lazy_local_getter_reuses_first_constructed(request):
    # we're not supposed to construct ContextVars inside functions because they can't
    # really be garbage-collected, but otherwise it's difficult to ensure we're getting
    # a "clean" ContextVar for this test
    cv = ContextVar(request.node.name)  # ensure name is unique across test session

    factory = mock.Mock(
        spec=("__call__",),
        side_effect=(getattr(mock.sentinel, f"some_object_{i}") for i in count()),
    )

    llg = LazyLocalGetter(cv, factory)

    assert llg() is mock.sentinel.some_object_0
    assert llg() is mock.sentinel.some_object_0

    assert factory.call_args_list == [mock.call()]  # despite two accesses


def test_lazy_local_getter_clear(request):
    # ...same caveat about locally-declared ContextVar...
    cv = ContextVar(request.node.name)  # ensure name is unique across test session

    factory = mock.Mock(
        spec=("__call__",),
        side_effect=(getattr(mock.sentinel, f"some_object_{i}") for i in count()),
    )

    llg = LazyLocalGetter(cv, factory)

    assert llg() is mock.sentinel.some_object_0
    assert factory.call_args_list == [mock.call()]
    factory.reset_mock()

    llg.clear()
    assert llg() is mock.sentinel.some_object_1
    assert factory.call_args_list == [mock.call()]
