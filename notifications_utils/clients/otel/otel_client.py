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
            otlp_host = self.config.get("OTEL_COLLECTOR_HOST", "localhost")
            otlp_port = self.config.get("OTEL_COLLECTOR_PORT", 4317)
            endpoint = f"{otlp_host}:{otlp_port}"
            otlp_exporter = OTLPMetricExporter(endpoint=endpoint, insecure=True)
            metric_readers.append(PeriodicExportingMetricReader(otlp_exporter))

        provider = MeterProvider(metric_readers=metric_readers)
        otel_metrics.set_meter_provider(provider)
        self.meter = otel_metrics.get_meter(__name__)

        # Internal cache for metrics
        self._metrics = {}

    def get_counter(self, name, description="", unit="1"):
        if name not in self._metrics:
            self._metrics[name] = self.meter.create_counter(
                name=name,
                description=description,
                unit=unit,
            )
        return self._metrics[name]

    def get_histogram(self, name, description="", unit="s"):
        if name not in self._metrics:
            self._metrics[name] = self.meter.create_histogram(
                name=name,
                description=description,
                unit=unit,
            )
        return self._metrics[name]

    def incr(self, name, value=1, attributes=None, description="", unit="1"):
        counter = self.get_counter(name, description, unit)
        counter.add(value, attributes or {})

    def record(self, name, value, attributes=None, description="", unit="s"):
        histogram = self.get_histogram(name, description, unit)
        histogram.record(value, attributes or {})
