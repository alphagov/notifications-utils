import os

from flask import Flask
from opentelemetry import metrics
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.processor.baggage import BaggageSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    ConsoleMetricExporter,
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.trace import get_tracer_provider, set_tracer_provider


def init_otel_app(app: Flask) -> None:
    """
    Initialize the OpenTelemetry instrumentation for the Flask app.
    """

    if getattr(app, "_otel_instrumented", False):
        app.logger.debug("OpenTelemetry instrumentation already applied, skipping.")
        return

    export_mode = app.config.get("OTEL_EXPORT_TYPE", "none").lower().strip()
    metric_readers = []

    if export_mode == "console":
        app.logger.info("OpenTelemetry metrics and spans will be exported to console")
        metric_readers.append(PeriodicExportingMetricReader(ConsoleMetricExporter()))
        span_processor = BatchSpanProcessor(ConsoleSpanExporter())
    elif export_mode == "otlp":
        endpoint = app.config.get("OTEL_COLLECTOR_ENDPOINT", "localhost:4317")
        app.logger.info("OpenTelemetry metrics and spans will be exported to OTLP collector at %s", endpoint)
        otlp_exporter = OTLPMetricExporter(endpoint=endpoint, insecure=True)
        metric_readers.append(PeriodicExportingMetricReader(otlp_exporter))

        os.environ["OTEL_METRIC_EXPORT_INTERVAL"] = app.config.get("OTEL_METRIC_EXPORT_INTERVAL", "15s")
        os.environ["OTEL_METRIC_EXPORT_TIMEOUT"] = app.config.get("OTEL_METRIC_EXPORT_TIMEOUT", "30s")

        span_processor = BatchSpanProcessor(
            OTLPSpanExporter(
                endpoint=endpoint,
                insecure=app.config.get("OTEL_COLLECTOR_INSECURE", True),
            )
        )
    elif export_mode == "none":
        app.logger.info("OpenTelemetry metrics and spans will not be exported")
        return
    else:
        raise ValueError(f"Invalid OTEL_EXPORT_TYPE: {export_mode}. Expected 'console', 'otlp', or 'none'.")

    resource = Resource.create(
        {"service.name": os.getenv("NOTIFY_APP_NAME") or app.config.get("NOTIFY_APP_NAME") or "notifications"}
    )

    provider = MeterProvider(metric_readers=metric_readers, resource=resource)
    metrics.set_meter_provider(provider)

    set_tracer_provider(TracerProvider(resource=resource))

    def regex_predicate(baggage_key: str) -> bool:
        return baggage_key.startswith("^public-.+")

    get_tracer_provider().add_span_processor(BaggageSpanProcessor(regex_predicate))
    get_tracer_provider().add_span_processor(span_processor)

    _instrument_app(app)

    app._otel_instrumented = True


def _instrument_app(app: Flask) -> None:
    """
    Apply OpenTelemetry instrumentation based on available optional dependencies.
    """

    # Affects both requests and Flask instrumentation
    os.environ["OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_SERVER_REQUEST"] = app.config.get(
        "OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_SERVER_REQUEST", ".*"
    )

    os.environ["OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_SERVER_RESPONSE"] = app.config.get(
        "OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_SERVER_RESPONSE", ".*"
    )

    os.environ["OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_SANITIZE_FIELDS"] = app.config.get(
        "OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_SANITIZE_FIELDS", "authorization,set-cookie,.*session.*"
    )

    instrument_map = {
        "celery": (_instrument_celery, "opentelemetry.instrumentation.celery"),
        "flask": (_instrument_flask, "opentelemetry.instrumentation.flask"),
        "redis": (_instrument_redis, "opentelemetry.instrumentation.redis"),
        "requests": (_instrument_requests, "opentelemetry.instrumentation.requests"),
        "sqlalchemy": (_instrument_sqlalchemy, "opentelemetry.instrumentation.sqlalchemy"),
        "botocore": (_instrument_botocore, "opentelemetry.instrumentation.botocore"),
    }

    for name, (func, module_name) in instrument_map.items():
        try:
            __import__(module_name)
            func(app)
            app.logger.info("Enabled OpenTelemetry instrumentation: %s", name)
        except ImportError:
            app.logger.debug("Optional instrumentation '%s' not installed, skipping.", name)


def _instrument_celery(app: Flask) -> None:
    from opentelemetry.instrumentation.celery import CeleryInstrumentor

    CeleryInstrumentor().instrument()


def _instrument_flask(app: Flask) -> None:
    from opentelemetry.instrumentation.flask import FlaskInstrumentor

    FlaskInstrumentor().instrument_app(
        app,
        excluded_urls=app.config.get("OTEL_PYTHON_FLASK_EXCLUDED_URLS", "_status(\\?.*)?$,/metrics"),
    )


def _instrument_redis(app: Flask) -> None:
    from opentelemetry.instrumentation.redis import RedisInstrumentor

    def redis_request_hook(span, conn, args, kwargs):
        if span and args and len(args) > 1:
            # For multi-key commands, keys are all args[1:]
            # For single-key commands, key is args[1]
            keys = []
            for arg in args[1:]:
                if isinstance(arg, str | bytes):
                    if isinstance(arg, bytes):
                        try:
                            arg = arg.decode("utf-8")
                        except Exception:
                            arg = repr(arg)
                    keys.append(arg)
                else:
                    # Stop at first non-key argument (e.g., value for SET)
                    break
            if keys:
                span.set_attribute("db.redis.keys", ",".join(keys))

    def redis_response_hook(span, *args, **kwargs):
        if span:
            span.update_name(f"redis/{span.name}")

    RedisInstrumentor().instrument(
        request_hook=redis_request_hook,
        response_hook=redis_response_hook,
    )


def _instrument_requests(app: Flask) -> None:
    from opentelemetry.instrumentation.requests import RequestsInstrumentor

    # Work around for span names not being unique in Requests instrumentation
    def requests_response_hook(span, *args, **kwargs):
        if span:
            span.update_name(f"requests/{span.name}")

    RequestsInstrumentor().instrument(response_hook=requests_response_hook)


def _instrument_sqlalchemy(app: Flask) -> None:
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

    SQLAlchemyInstrumentor().instrument(enable_commenter=True, commenter_options={})


def _instrument_botocore(app: Flask) -> None:
    from opentelemetry.instrumentation.botocore import BotocoreInstrumentor

    BotocoreInstrumentor().instrument()
