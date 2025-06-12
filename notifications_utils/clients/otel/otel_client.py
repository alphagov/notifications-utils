from opentelemetry import metrics as otel_metrics
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    ConsoleMetricExporter,
    PeriodicExportingMetricReader,
)


class OtelClient:
    def init_app(self, app):
        self.config = app.config

        app.otel_client = self

        export_mode = self.config.get("OTEL_METRICS_EXPORT", "none").lower()
        metric_readers = []

        if export_mode == "console":
            app.logger.info("OpenTelemetry metrics will be exported to console")
            metric_readers.append(PeriodicExportingMetricReader(ConsoleMetricExporter()))
        elif export_mode == "otlp":
            endpoint = self.config.get("OTEL_COLLECTOR_ENDPOINT", "localhost:4317")
            otlp_exporter = OTLPMetricExporter(endpoint=endpoint, insecure=True)
            # Metrics will be exported every 60 seconds with a 30 seconds timeout by default.
            # The following environments variables can be used to change this:
            # OTEL_METRIC_EXPORT_INTERVAL
            # OTEL_METRIC_EXPORT_TIMEOUT
            metric_readers.append(PeriodicExportingMetricReader(otlp_exporter))

        provider = MeterProvider(metric_readers=metric_readers)
        otel_metrics.set_meter_provider(provider)
        self.meter = otel_metrics.get_meter(__name__)

        # Internal cache for metrics
        self._metrics = {}

    def get_meter(self):
        if not hasattr(self, "meter"):
            raise RuntimeError("OpenTelemetry meter is not initialized. Call init_app first.")
        return self.meter

    def get_counter(self, name, description="", unit="count"):
        if name not in self._metrics:
            self._metrics[name] = self.get_meter().create_counter(
                name=name,
                description=description,
                unit=unit,
            )
        return self._metrics[name]

    def get_histogram(self, name, description="", unit="seconds", buckets=None):
        if name not in self._metrics:
            if buckets is None:
                buckets = [
                    0.005,
                    0.01,
                    0.025,
                    0.05,
                    0.075,
                    0.1,
                    0.25,
                    0.5,
                    0.75,
                    1.0,
                    2.5,
                    5.0,
                    7.5,
                    10.0,
                    float("inf"),
                ]
            self._metrics[name] = self.get_meter().create_histogram(
                name=name,
                description=description,
                unit=unit,
                explicit_bucket_boundaries_advisory=buckets,
            )
        return self._metrics[name]

    def get_gauge(self, name, description="", unit=""):
        if name not in self._metrics:
            self._metrics[name] = self.get_meter().create_gauge(
                name=name,
                description=description,
                unit=unit,
            )
        return self._metrics[name]

    def incr(self, name, value=1, attributes=None, description="", unit="count"):
        counter = self.get_counter(name, description, unit)
        counter.add(value, attributes or {})

    def record(self, name, value, attributes=None, description="", unit="seconds", buckets=None):
        histogram = self.get_histogram(name, description, unit, buckets)
        histogram.record(value, attributes or {})

    def gauge(self, name, value, attributes=None, description="", unit=""):
        gauge = self.get_gauge(name, description, unit)
        gauge.record(value, attributes or {})
