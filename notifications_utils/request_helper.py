from itertools import chain
from random import SystemRandom

from flask import request, current_app


class RequestIdRequestMixin(object):
    """
        A mixin intended for use against a flask Request class, implementing extraction (and partly generation) of
        headers approximately according to the "zipkin" scheme https://github.com/openzipkin/b3-propagation
    """
    # a single class-wide random instance should be good enough for now
    _spanid_random = _traceid_random = SystemRandom()

    @property
    def request_id(self):
        return self.trace_id

    @property
    def trace_id(self):
        """
            The "trace id" (in zipkin terms) assigned to this request. If one was set in the request header, that will
            be used. Failing that, this will be an id we've generated and assigned ourselves.
        """
        if not hasattr(self, "_trace_id"):
            self._trace_id = self._get_first_header(
                current_app.config['NOTIFY_TRACE_ID_HEADERS']
            ) or self._get_new_trace_id()
        return self._trace_id

    @property
    def span_id(self):
        """
            The "span id" (in zipkin terms) set in this request's header, if present (None otherwise)
        """
        if not hasattr(self, "_span_id"):
            # note how we don't generate an id of our own. not being supplied a span id implies that we are running in
            # an environment with no span-id-aware request router, and thus would have no intermediary to prevent the
            # propagation of our span id all the way through all our onwards requests much like trace id. and the point
            # of span id is to assign identifiers to each individual request.
            self._span_id = self._get_first_header(current_app.config['NOTIFY_SPAN_ID_HEADERS'])
        return self._span_id

    @property
    def parent_span_id(self):
        """
            The "parent span id" (in zipkin terms) set in this request's header, if present (None otherwise)
        """
        if not hasattr(self, "_parent_span_id"):
            self._parent_span_id = self._get_first_header(current_app.config['NOTIFY_PARENT_SPAN_ID_HEADERS'])
        return self._parent_span_id

    @property
    def is_sampled(self):
        if not hasattr(self, "_is_sampled"):
            header_value = self._get_first_header(current_app.config['NOTIFY_IS_SAMPLED_HEADERS'])
            self._is_sampled = self.debug_flag or (None if header_value is None else header_value == "1")
        return self._is_sampled

    @property
    def debug_flag(self):
        if not hasattr(self, "_debug_flag"):
            header_value = self._get_first_header(current_app.config['NOTIFY_DEBUG_FLAG_HEADERS'])
            self._debug_flag = None if header_value is None else header_value == "1"
        return self._debug_flag

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
        return hex(self._traceid_random.randrange(1 << 128))[2:]

    def _get_new_span_id(self):
        return hex(self._spanid_random.randrange(1 << 64))[2:]

    def get_onwards_request_headers(self):
        """
            Headers to add to any further (internal) http api requests we perform if we want that request to be
            considered part of this "trace id"
        """
        new_span_id = self._get_new_span_id()
        return dict(chain(
            (
                (header_name, self.trace_id)
                for header_name in current_app.config['NOTIFY_TRACE_ID_HEADERS']
            ) if self.trace_id else (),
            (
                (header_name, new_span_id)
                for header_name in current_app.config['NOTIFY_SPAN_ID_HEADERS']
            ) if self.trace_id else (),
            (
                (header_name, self.span_id)
                for header_name in current_app.config['NOTIFY_PARENT_SPAN_ID_HEADERS']
            ) if self.span_id else (),
            (
                (header_name, "1" if self.is_sampled else "0")
                for header_name in current_app.config['NOTIFY_IS_SAMPLED_HEADERS']
                # according to zipkin spec we shouldn't propagate the sampling decision if debug_flag is set
            ) if self.is_sampled is not None and not self.debug_flag else (),
            (
                (header_name, "1" if self.debug_flag else "0")
                for header_name in current_app.config['NOTIFY_DEBUG_FLAG_HEADERS']
            ) if self.debug_flag is not None else (),
        ))

    def get_extra_log_context(self):
        """
            extra attributes to be made available on a log record based on this request
        """
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            # output these as 1|0 strings to match what's easily outputtable by nginx
            "is_sampled": "1" if self.is_sampled else "0",
            "debug_flag": "1" if self.debug_flag else "0",
        }


class ResponseHeaderMiddleware(object):
    def __init__(self, app, trace_id_headers, span_id_headers):
        self.app = app
        self.trace_id_headers = trace_id_headers
        self.span_id_headers = span_id_headers

    def __call__(self, environ, start_response):
        def rewrite_response_headers(status, headers, exc_info=None):
            lower_existing_header_names = frozenset(name.lower() for name, value in headers)
            headers.extend(chain(
                (
                    (header_name, str(request.trace_id),)
                    for header_name in self.trace_id_headers
                    if header_name.lower() not in lower_existing_header_names
                ),
                (
                    (header_name, str(request.span_id),)
                    for header_name in self.span_id_headers
                    if header_name.lower() not in lower_existing_header_names
                ),
            ))

            return start_response(status, headers, exc_info)

        return self.app(environ, rewrite_response_headers)


def init_app(app):
    app.config.setdefault("NOTIFY_TRACE_ID_HEADERS", (
        (app.config.get("NOTIFY_REQUEST_ID_HEADER") or "Notify-Request-ID"),
        (app.config.get("NOTIFY_DOWNSTREAM_REQUEST_ID_HEADER") or "X-B3-TraceId"),
    ))
    app.config.setdefault("NOTIFY_SPAN_ID_HEADERS", ("X-B3-SpanId",))
    app.config.setdefault("NOTIFY_PARENT_SPAN_ID_HEADERS", ("X-B3-ParentSpanId",))
    app.config.setdefault("NOTIFY_IS_SAMPLED_HEADERS", ("X-B3-Sampled",))
    app.config.setdefault("NOTIFY_DEBUG_FLAG_HEADERS", ("X-B3-Flags",))

    # we do something a little odd here now - back-populate the first value of NOTIFY_TRACE_ID_HEADERS back to the
    # NOTIFY_REQUEST_ID_HEADER setting, because it turns out that some components (notably the apiclient) depend on that
    # setting
    if app.config.get("NOTIFY_TRACE_ID_HEADERS"):
        app.config["NOTIFY_REQUEST_ID_HEADER"] = app.config["NOTIFY_TRACE_ID_HEADERS"][0]

    # dynamically define this class as we don't necessarily know how request_class may have already been modified by
    # another init_app
    class _RequestIdRequest(RequestIdRequestMixin, app.request_class):
        pass
    app.request_class = _RequestIdRequest
    app.wsgi_app = ResponseHeaderMiddleware(
        app.wsgi_app,
        app.config['NOTIFY_TRACE_ID_HEADERS'],
        app.config['NOTIFY_SPAN_ID_HEADERS'],
    )


def check_proxy_header_before_request():
    keys = [
        current_app.config.get('ROUTE_SECRET_KEY_1'),
        current_app.config.get('ROUTE_SECRET_KEY_2'),
    ]
    result, msg = _check_proxy_header_secret(request, keys)

    if not result:
        current_app.logger.warning(msg)
        if current_app.config.get('CHECK_PROXY_HEADER', False):
            abort(403)

    # We need to return None to continue processing the request
    # http://flask.pocoo.org/docs/0.12/api/#flask.Flask.before_request
    return None


def _check_proxy_header_secret(request, secrets, header='X-Custom-Forwarder'):
    if header not in request.headers:
        return False, "Header missing"

    header_secret = request.headers.get(header)
    if not header_secret:
        return False, "Header exists but is empty"

    # if there isn't any non-empty secret configured we fail closed
    if not any(secrets):
        return False, "Secrets are not configured"

    for i, secret in enumerate(secrets):
        if header_secret == secret:
            return True, "Key used: {}".format(i + 1)  # add 1 to make it human-compatible

    return False, "Header didn't match any keys"
