from itertools import chain

from flask import request, current_app


class RequestIdRequestMixin(object):
    """
        A mixin intended for use against a flask Request class, implementing extraction (and partly generation) of
        headers approximately according to the "zipkin" scheme https://github.com/openzipkin/b3-propagation
    """

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
            )
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

    def _get_first_header(self, header_names):
        """
        Returns value of request's first present (and Truthy) header from header_names
        """
        for header_name in header_names:
            if header_name in self.headers and self.headers[header_name]:
                return self.headers[header_name]
        else:
            return None


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
    app.config.setdefault("NOTIFY_TRACE_ID_HEADERS", ("X-B3-TraceId",))
    app.config.setdefault("NOTIFY_SPAN_ID_HEADERS", ("X-B3-SpanId",))
    app.config.setdefault("NOTIFY_PARENT_SPAN_ID_HEADERS", ("X-B3-ParentSpanId",))

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
