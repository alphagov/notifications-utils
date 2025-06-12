from unittest.mock import MagicMock, patch

import pytest

from notifications_utils.clients.otel.otel_client import OtelClient


@pytest.fixture
def config_console():
    return {"OTEL_METRICS_EXPORT": "console"}


@pytest.fixture
def config_none():
    return {"OTEL_METRICS_EXPORT": "none"}


@pytest.fixture
def config_otlp():
    return {"OTEL_METRICS_EXPORT": "otlp", "OTEL_COLLECTOR_ENDPOINT": "test-endpoint:4317"}


@pytest.fixture
def fake_app():
    app = MagicMock()
    app.config = {}
    app.logger.info = MagicMock()
    return app


def test_meter_and_cache_created_console(config_console, fake_app):
    fake_app.config = config_console
    with (
        patch("opentelemetry.sdk.metrics.export.ConsoleMetricExporter"),
        patch("opentelemetry.sdk.metrics.export.PeriodicExportingMetricReader"),
        patch("opentelemetry.sdk.metrics.MeterProvider"),
        patch("opentelemetry.metrics.set_meter_provider"),
        patch("opentelemetry.metrics.get_meter", return_value=MagicMock()) as mock_get_meter,
    ):
        client = OtelClient()
        client.init_app(fake_app)
        assert hasattr(client, "meter")
        assert client._metrics == {}
        assert client.get_meter() is client.meter
        assert client.get_meter() is mock_get_meter.return_value


def test_meter_and_cache_created_otlp(config_otlp, fake_app):
    fake_app.config = config_otlp
    with (
        patch("notifications_utils.clients.otel.otel_client.OTLPMetricExporter") as mock_exporter,
        patch("opentelemetry.sdk.metrics.export.PeriodicExportingMetricReader"),
        patch("opentelemetry.sdk.metrics.MeterProvider"),
        patch("opentelemetry.metrics.set_meter_provider"),
        patch("opentelemetry.metrics.get_meter", return_value=MagicMock()),
    ):
        client = OtelClient()
        client.init_app(fake_app)
        mock_exporter.assert_called_with(endpoint="test-endpoint:4317", insecure=True)
        assert hasattr(client, "meter")
        assert client._metrics == {}


def test_get_counter_and_incr(config_none, fake_app):
    fake_app.config = config_none
    with (
        patch("opentelemetry.sdk.metrics.MeterProvider"),
        patch("opentelemetry.metrics.set_meter_provider"),
        patch("opentelemetry.metrics.get_meter") as mock_get_meter,
    ):
        mock_meter = MagicMock()
        mock_counter = MagicMock()
        mock_meter.create_counter.return_value = mock_counter
        mock_get_meter.return_value = mock_meter

        client = OtelClient()
        client.init_app(fake_app)
        counter = client.get_counter("my_counter", "desc", "1")
        assert counter is mock_counter

        counter.incr("my_counter", value=2, attributes={"foo": "bar"})
        mock_counter.incr.assert_called_with("my_counter", value=2, attributes={"foo": "bar"})


def test_counter_direct_add(config_none, fake_app):
    fake_app.config = config_none
    with (
        patch("opentelemetry.sdk.metrics.MeterProvider"),
        patch("opentelemetry.metrics.set_meter_provider"),
        patch("opentelemetry.metrics.get_meter") as mock_get_meter,
    ):
        mock_meter = MagicMock()
        mock_counter = MagicMock()
        mock_meter.create_counter.return_value = mock_counter
        mock_get_meter.return_value = mock_meter

        client = OtelClient()
        client.init_app(fake_app)
        counter = client.get_counter("direct_counter")
        counter.add(10, {"direct": "yes"})
        mock_counter.add.assert_called_with(10, {"direct": "yes"})


def test_histogram_direct_record(config_none, fake_app):
    fake_app.config = config_none
    with (
        patch("opentelemetry.sdk.metrics.MeterProvider"),
        patch("opentelemetry.metrics.set_meter_provider"),
        patch("opentelemetry.metrics.get_meter") as mock_get_meter,
    ):
        mock_meter = MagicMock()
        mock_histogram = MagicMock()
        mock_meter.create_histogram.return_value = mock_histogram
        mock_get_meter.return_value = mock_meter

        client = OtelClient()
        client.init_app(fake_app)
        histogram = client.get_histogram("direct_hist")
        histogram.record(3.14, {"direct": "yes"})
        mock_histogram.record.assert_called_with(3.14, {"direct": "yes"})


def test_gauge_direct_record(config_none, fake_app):
    fake_app.config = config_none
    with (
        patch("opentelemetry.sdk.metrics.MeterProvider"),
        patch("opentelemetry.metrics.set_meter_provider"),
        patch("opentelemetry.metrics.get_meter") as mock_get_meter,
    ):
        mock_meter = MagicMock()
        mock_gauge = MagicMock()
        mock_meter.create_gauge.return_value = mock_gauge
        mock_get_meter.return_value = mock_meter

        client = OtelClient()
        client.init_app(fake_app)
        gauge = client.get_gauge("direct_gauge")
        gauge.record(99, {"direct": "yes"})
        mock_gauge.record.assert_called_with(99, {"direct": "yes"})


def test_record(config_none, fake_app):
    fake_app.config = config_none
    with (
        patch("opentelemetry.sdk.metrics.MeterProvider"),
        patch("opentelemetry.metrics.set_meter_provider"),
        patch("opentelemetry.metrics.get_meter") as mock_get_meter,
    ):
        mock_meter = MagicMock()
        mock_histogram = MagicMock()
        mock_meter.create_histogram.return_value = mock_histogram
        mock_get_meter.return_value = mock_meter

        client = OtelClient()
        client.init_app(fake_app)

        client.record("my_hist", value=1.23, attributes={"foo": "bar"})
        mock_histogram.record.assert_called_with(1.23, {"foo": "bar"})


def test_gauge(config_none, fake_app):
    fake_app.config = config_none
    with (
        patch("opentelemetry.sdk.metrics.MeterProvider"),
        patch("opentelemetry.metrics.set_meter_provider"),
        patch("opentelemetry.metrics.get_meter") as mock_get_meter,
    ):
        mock_meter = MagicMock()
        mock_gauge = MagicMock()
        mock_meter.create_gauge.return_value = mock_gauge
        mock_get_meter.return_value = mock_meter

        client = OtelClient()
        client.init_app(fake_app)

        client.gauge("my_gauge", value=42, attributes={"foo": "bar"})
        mock_gauge.set.assert_called_with(42, {"foo": "bar"})


def test_counter(config_none, fake_app):
    fake_app.config = config_none
    with (
        patch("opentelemetry.sdk.metrics.MeterProvider"),
        patch("opentelemetry.metrics.set_meter_provider"),
        patch("opentelemetry.metrics.get_meter") as mock_get_meter,
    ):
        mock_meter = MagicMock()
        mock_counter = MagicMock()
        mock_meter.create_counter.return_value = mock_counter
        mock_get_meter.return_value = mock_meter

        client = OtelClient()
        client.init_app(fake_app)

        client.incr("my_counter", attributes={"foo": "bar"})
        mock_counter.add.assert_called_with(1, {"foo": "bar"})

        client.incr("my_counter", value=5, attributes={"foo": "bar"})
        mock_counter.add.assert_called_with(5, {"foo": "bar"})


def test_without_mocks_otel(config_none, fake_app):
    fake_app.config = config_none

    client = OtelClient()
    client.init_app(fake_app)

    client.incr("actual_counter", attributes={"test": "value"})
    client.record("actual_histogram", value=2.5, attributes={"test": "value"})
    client.gauge("actual_gauge", value=10, attributes={"test": "value"})

    client.get_counter("actual_counter").add(3, {"test": "value"})
    client.get_histogram("actual_histogram").record(1.5, {"test": "value"})
    client.get_gauge("actual_gauge").set(20, {"test": "value"})
