from unittest.mock import MagicMock, patch

import pytest

from notifications_utils.clients.otel.utils import otel_duration_histogram, otel_span_with_status


def test_otel_span_with_status_as_decorator_success():
    mock_tracer = MagicMock()
    mock_span = MagicMock()
    mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span

    @otel_span_with_status(mock_tracer, "test-span-decorator", service="test")
    def test_func(x):
        return x * 2

    result = test_func(5)
    assert result == 10
    mock_span.set_attribute.assert_any_call("service", "test")
    mock_span.set_status.assert_not_called()
    mock_span.record_exception.assert_not_called()


def test_otel_span_with_status_as_decorator_exception():
    mock_tracer = MagicMock()
    mock_span = MagicMock()
    mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span

    @otel_span_with_status(mock_tracer, "test-span-decorator", operation="failing")
    def test_func():
        raise ValueError("test error")

    with pytest.raises(ValueError, match="test error"):
        test_func()

    mock_span.set_attribute.assert_any_call("operation", "failing")
    mock_span.record_exception.assert_called()
    mock_span.set_status.assert_called()


def test_otel_span_with_status_as_decorator_no_attributes():
    mock_tracer = MagicMock()
    mock_span = MagicMock()
    mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span

    @otel_span_with_status(mock_tracer, "simple-span")
    def test_func(a, b):
        return a + b

    result = test_func(3, 4)
    assert result == 7
    # Should not call set_attribute since no attributes were provided
    mock_span.set_attribute.assert_not_called()
    mock_span.set_status.assert_not_called()


def test_otel_span_with_status_as_decorator_multiple_attributes():
    mock_tracer = MagicMock()
    mock_span = MagicMock()
    mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span

    @otel_span_with_status(mock_tracer, "multi-attr-span", user_id="123", operation="update", priority="high")
    def test_func():
        return "success"

    result = test_func()
    assert result == "success"
    mock_span.set_attribute.assert_any_call("user_id", "123")
    mock_span.set_attribute.assert_any_call("operation", "update")
    mock_span.set_attribute.assert_any_call("priority", "high")
    assert mock_span.set_attribute.call_count == 3


def test_otel_span_with_status_success():
    mock_tracer = MagicMock()
    mock_span = MagicMock()
    mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span

    with otel_span_with_status(mock_tracer, "test-span", foo="bar") as span:
        assert span is mock_span
    mock_span.set_attribute.assert_any_call("foo", "bar")
    mock_span.set_status.assert_not_called()


def test_otel_span_with_status_exception():
    mock_tracer = MagicMock()
    mock_span = MagicMock()
    mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span

    with pytest.raises(RuntimeError):
        with otel_span_with_status(mock_tracer, "test-span", foo="bar"):
            raise RuntimeError("fail!")
    mock_span.record_exception.assert_called()
    mock_span.set_status.assert_called()


def test_otel_duration_histogram_records_success():
    mock_meter = MagicMock()
    mock_histogram = MagicMock()
    mock_meter.create_histogram.return_value = mock_histogram

    with patch("notifications_utils.clients.otel.utils.get_meter", return_value=mock_meter):

        @otel_duration_histogram("test_histogram", attributes={"foo": "bar"})
        def test_func(x):
            return x + 1

        result = test_func(2)
        assert result == 3
        # Should record with status "success"
        mock_histogram.record.assert_called()
        args, kwargs = mock_histogram.record.call_args
        assert kwargs["attributes"]["foo"] == "bar"
        assert kwargs["attributes"]["status"] == "success"


def test_otel_duration_histogram_records_error():
    mock_meter = MagicMock()
    mock_histogram = MagicMock()
    mock_meter.create_histogram.return_value = mock_histogram

    with patch("notifications_utils.clients.otel.utils.get_meter", return_value=mock_meter):

        @otel_duration_histogram("test_histogram")
        def test_func():
            raise RuntimeError("fail!")

        with pytest.raises(RuntimeError):
            test_func()
        # Should record with status "error"
        mock_histogram.record.assert_called()
        _, kwargs = mock_histogram.record.call_args
        assert kwargs["attributes"]["status"] == "error"


def test_otel_duration_histogram_dynamic_attributes():
    mock_meter = MagicMock()
    mock_histogram = MagicMock()
    mock_meter.create_histogram.return_value = mock_histogram

    with patch("notifications_utils.clients.otel.utils.get_meter", return_value=mock_meter):

        @otel_duration_histogram("test_histogram", attributes=lambda args, kwargs: {"arg": args[0]})
        def test_func(x):
            return x * 2

        test_func(5)
        mock_histogram.record.assert_called()
        _, kwargs = mock_histogram.record.call_args
        assert kwargs["attributes"]["arg"] == 5
        assert kwargs["attributes"]["status"] == "success"
