from itertools import chain
from random import SystemRandom

from flask import current_app, request
from flask.wrappers import Request


class NotifyRequest(Request):
    """
    A custom Request class, implementing extraction of zipkin headers used to trace request through cloudfoundry
    as described here: https://docs.cloudfoundry.org/concepts/http-routing.html#zipkin-headers
    """

    # a single class-wide random instance should be good enough for now
    _spanid_random = _traceid_random = SystemRandom()

    @property
    def request_id(self):
        return self.trace_id

    @property
    def trace_id(self):
        """
        The "trace id" (in zipkin terms) assigned to this request. If not present, will
        generate its own.
        """
        if not hasattr(self, "_trace_id"):
            self._trace_id = (
                self._get_first_header(
                    chain(
                        (current_app.config["NOTIFY_TRACE_ID_HEADER"],),
                        current_app.config["NOTIFY_TRACE_ID_ALT_HEADERS"],
                    )
                )
                or self._get_new_trace_id()
            )
        return self._trace_id

    @property
    def span_id(self):
        """
        The "span id" (in zipkin terms) set in this request's header. If not present, will
        generate its own prefixed with "self-".
        """
        if not hasattr(self, "_span_id"):
            self._span_id = (
                self._get_first_header(
                    chain(
                        (current_app.config["NOTIFY_SPAN_ID_HEADER"],),
                        current_app.config["NOTIFY_SPAN_ID_ALT_HEADERS"],
                    )
                )
                or f"self-{self._get_new_span_id()}"
            )
        return self._span_id

    @property
    def parent_span_id(self):
        """
        The "parent span id" (in zipkin terms) set in this request's header, if present (None otherwise)
        """
        if not hasattr(self, "_parent_span_id"):
            self._parent_span_id = self._get_first_header(
                chain(
                    (current_app.config["NOTIFY_PARENT_SPAN_ID_HEADER"],),
                    current_app.config["NOTIFY_PARENT_SPAN_ID_ALT_HEADERS"],
                )
            )
        return self._parent_span_id

    def _get_header_value(self, header_name):
        """
        Returns value of the given header
        """
        if header_name in self.headers and self.headers[header_name]:
            return self.headers[header_name]

        return None

    def _get_first_header(self, header_names):
        """
        Returns value of request's first present (and Truthy) header from header_names
        """
        for header_name in header_names:
            if header_name in self.headers and self.headers[header_name]:
                return self.headers[header_name]
        else:
            return None

    def _get_new_trace_id(self):
        "Generate a random zipkin-compliant trace id"
        bitlen = 128
        return hex(self._traceid_random.randrange(1 << bitlen))[2:].rjust(bitlen // 4, "0")

    def _get_new_span_id(self):
        "Generate a random zipkin-compliant span id"
        bitlen = 64
        return hex(self._spanid_random.randrange(1 << bitlen))[2:].rjust(bitlen // 4, "0")

    def get_onwards_request_headers(self):
        """
        Headers to add to any further (internal) http api requests we perform if we want that request to be
        considered part of this "trace id"
        """
        new_span_id = self._get_new_span_id()
        return dict(
            chain(
                ((current_app.config["NOTIFY_TRACE_ID_HEADER"], self.trace_id),) if self.trace_id else (),
                ((current_app.config["NOTIFY_SPAN_ID_HEADER"], new_span_id),) if self.trace_id else (),
                ((current_app.config["NOTIFY_PARENT_SPAN_ID_HEADER"], self.span_id),) if self.span_id else (),
            )
        )


class ResponseHeaderMiddleware:
    def __init__(self, app, trace_id_header, span_id_header):
        self.app = app
        self.trace_id_header = trace_id_header
        self.span_id_header = span_id_header

    def __call__(self, environ, start_response):
        def rewrite_response_headers(status, headers, exc_info=None):
            lower_existing_header_names = frozenset(name.lower() for name, value in headers)

            if self.trace_id_header not in lower_existing_header_names:
                headers.append((self.trace_id_header, str(request.trace_id)))

            if self.span_id_header not in lower_existing_header_names:
                headers.append((self.span_id_header, str(request.span_id)))

            return start_response(status, headers, exc_info)

        return self.app(environ, rewrite_response_headers)


def init_app(app):
    app.config.setdefault("NOTIFY_TRACE_ID_HEADER", "X-B3-TraceId")
    app.config.setdefault(
        "NOTIFY_TRACE_ID_ALT_HEADERS",
        (
            "X-Amz-Cf-Id",  # from cloudfront
            "X-Amzn-Trace-Id",  # from load balancer
        ),
    )
    app.config.setdefault("NOTIFY_SPAN_ID_HEADER", "X-B3-SpanId")
    app.config.setdefault("NOTIFY_SPAN_ID_ALT_HEADERS", ())
    app.config.setdefault("NOTIFY_PARENT_SPAN_ID_HEADER", "X-B3-ParentSpanId")
    app.config.setdefault("NOTIFY_PARENT_SPAN_ID_ALT_HEADERS", ())

    app.request_class = NotifyRequest
    app.wsgi_app = ResponseHeaderMiddleware(
        app.wsgi_app,
        app.config["NOTIFY_TRACE_ID_HEADER"],
        app.config["NOTIFY_SPAN_ID_HEADER"],
    )
