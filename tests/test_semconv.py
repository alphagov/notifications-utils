import pytest
from opentelemetry.util.types import AttributeValue

from notifications_utils.semconv import set_error_type


class MyException(Exception):
    pass


def test_set_error_type_without_exception() -> None:
    try:
        pass
    finally:
        attributes: dict[str, AttributeValue] = {"foo.bar": "baz"}
        set_error_type(attributes)
        assert attributes == {"foo.bar": "baz"}


def test_set_error_type_with_exception() -> None:
    with pytest.raises(MyException):
        try:
            raise MyException
        finally:
            attributes: dict[str, AttributeValue] = {"foo.bar": "baz"}
            set_error_type(attributes)
            assert attributes == {
                "foo.bar": "baz",
                "error.type": "tests.test_semconv.MyException",
            }
