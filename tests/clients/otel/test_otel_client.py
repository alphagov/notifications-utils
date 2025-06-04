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
        patch("opentelemetry.metrics.get_meter", return_value=MagicMock()),
    ):
        client = OtelClient()
        client.init_app(fake_app)
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
        # Should use cache
        counter2 = client.get_counter("my_counter")
        assert counter2 is mock_counter

        client.incr("my_counter", value=2, attributes={"foo": "bar"})
        mock_counter.add.assert_called_with(2, {"foo": "bar"})


def test_get_histogram_and_record(config_none, fake_app):
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
        histogram = client.get_histogram("my_hist", "desc", "s")
        assert histogram is mock_histogram
        # Should use cache
        histogram2 = client.get_histogram("my_hist")
        assert histogram2 is mock_histogram

        client.record("my_hist", value=1.23, attributes={"foo": "bar"})
        mock_histogram.record.assert_called_with(1.23, {"foo": "bar"})
