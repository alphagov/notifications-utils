import os

import pytest
from opentelemetry.util.types import AttributeValue
from pytest_mock import MockerFixture

from notifications_utils.semconv import set_error_type, set_service_instance_id


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


def test_set_service_instance_id(mocker: MockerFixture) -> None:
    mocker.patch("notifications_utils.semconv.uuid4", return_value="00000000-0000-0000-0000-000000000000")
    set_service_instance_id()
    assert os.environ["OTEL_RESOURCE_ATTRIBUTES"] == "service.instance.id=00000000-0000-0000-0000-000000000000"


def test_set_service_instance_id_retains_existing_resource_attributes(mocker: MockerFixture) -> None:
    mocker.patch("notifications_utils.semconv.uuid4", return_value="00000000-0000-0000-0000-000000000000")
    os.environ["OTEL_RESOURCE_ATTRIBUTES"] = "foo=bar"
    set_service_instance_id()
    assert os.environ["OTEL_RESOURCE_ATTRIBUTES"] == "foo=bar,service.instance.id=00000000-0000-0000-0000-000000000000"
