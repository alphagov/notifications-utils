from itertools import chain, product
from unittest import mock

import pytest
from flask import Flask, request

from notifications_utils import request_helper
from notifications_utils.testing.comparisons import AnySupersetOf


def test_request_id_is_set_on_response(app):
    request_helper.init_app(app)
    client = app.test_client()

    with app.app_context():
        response = client.get("/", headers={"X-B3-TraceId": "generated", "X-B3-SpanId": "generated"})
        assert response.headers["X-B3-TraceId"] == "generated"
        assert response.headers["X-B3-SpanId"] == "generated"


def test_request_id_is_set_on_error_response(app):
    request_helper.init_app(app)
    client = app.test_client()
    # turn off DEBUG so that the flask default error handler gets triggered
    app.config["DEBUG"] = False

    @app.route("/")
    def error_route():
        raise Exception

    with app.app_context():
        response = client.get("/", headers={"X-B3-TraceId": "generated", "X-B3-SpanId": "generated"})
        assert response.status_code == 500
        assert response.headers["X-B3-TraceId"] == "generated"
        assert response.headers["X-B3-SpanId"] == "generated"


_GENERATED_TRACE_VALUE = 0xD15EA5E5DEADBEEFBAADF00DABADCAFE
_GENERATED_SPAN_VALUE = 0xC001D00DBEEFCACE

_GENERATED_TRACE_HEX = hex(_GENERATED_TRACE_VALUE)[2:]
_GENERATED_SPAN_HEX = hex(_GENERATED_SPAN_VALUE)[2:]


def _abbreviate_id(value):
    if value == _GENERATED_TRACE_VALUE:
        return "GEN_TRACE_VAL"
    elif value == _GENERATED_SPAN_VALUE:
        return "GEN_SPAN_VAL"
    elif value == ():
        return "EMPTYTUP"
    elif value == {}:
        return "EMPTYDCT"


_trace_id_related_params = (
    (
        # extra_config
        {
            "NOTIFY_TRACE_ID_HEADER": "X-B3-TraceId",
            "NOTIFY_TRACE_ID_ALT_HEADERS": ("Alt-Header-1", "Alt-Header-2"),
        },
        # extra_req_headers
        (
            (
                "X-B3-TRACEID",
                "from-header",
            ),
            (
                "alt-header-1",
                "from-alt-1",
            ),
        ),
        # expected_trace_id
        "from-header",
        # expect_trace_random_call
        False,
        # expected_onwards_req_headers
        {
            "X-B3-TraceId": "from-header",
        },
        # expected_resp_headers
        {
            "X-B3-TraceId": "from-header",
        },
    ),
    (
        # extra_config
        {
            "NOTIFY_TRACE_ID_HEADER": "X-B3-TraceId",
            "NOTIFY_TRACE_ID_ALT_HEADERS": ("Alt-Header-1", "Alt-Header-2"),
        },
        # extra_req_headers
        (
            (
                "alt-header-1",
                "from-alt-1",
            ),
            (
                "alt-header-2",
                "from-alt-2",
            ),
        ),
        # expected_trace_id
        "from-alt-1",
        # expect_trace_random_call
        False,
        # expected_onwards_req_headers
        {
            "X-B3-TraceId": "from-alt-1",
        },
        # expected_resp_headers
        {
            "X-B3-TraceId": "from-alt-1",
        },
    ),
    (
        # extra_config
        {
            "NOTIFY_TRACE_ID_HEADER": "X-B3-TraceId",
            "NOTIFY_TRACE_ID_ALT_HEADERS": (),
        },
        # extra_req_headers
        (),
        # expected_trace_id
        _GENERATED_TRACE_HEX,
        # expect_trace_random_call
        True,
        # expected_onwards_req_headers
        {
            "X-B3-TraceId": _GENERATED_TRACE_HEX,
        },
        # expected_resp_headers
        {
            "X-B3-TraceId": _GENERATED_TRACE_HEX,
        },
    ),
    (
        # extra_config
        {
            "NOTIFY_TRACE_ID_HEADER": "X-B3000-TraceId",
            "NOTIFY_TRACE_ID_ALT_HEADERS": ("Alt-Header-1",),
        },
        # extra_req_headers
        (),
        # expected_trace_id
        _GENERATED_TRACE_HEX,
        # expect_trace_random_call
        True,
        # expected_onwards_req_headers
        {
            "X-B3000-TraceId": _GENERATED_TRACE_HEX,
        },
        # expected_resp_headers
        {
            "X-B3000-TraceId": _GENERATED_TRACE_HEX,
        },
    ),
)

_span_id_related_params = (
    (
        # extra_config
        {},
        # extra_req_headers
        (
            (
                "x-b3-spanid",  # also checking header case-insensitivity here
                "Steak, kidney, liver, mashed",
            ),
            (
                "x-b3-parentspanid",
                "Muttoning",
            ),
        ),
        # expected_span_id
        "Steak, kidney, liver, mashed",
        # expected_parent_span_id
        "Muttoning",
        # expect_span_random_call_self
        False,
        # expected_onwards_req_headers
        {
            "X-B3-SpanId": _GENERATED_SPAN_HEX,
            "X-B3-ParentSpanId": "Steak, kidney, liver, mashed",
        },
        # expected_resp_headers
        {
            "X-B3-SpanId": "Steak, kidney, liver, mashed",
        },
    ),
    (
        # extra_config
        {},
        # extra_req_headers
        (),
        # expected_span_id
        f"self-{_GENERATED_SPAN_HEX}",
        # expected_parent_span_id
        None,
        # expect_span_random_call_self
        True,
        # expected_onwards_req_headers
        {
            "X-B3-SpanId": _GENERATED_SPAN_HEX,
            "X-B3-ParentSpanId": f"self-{_GENERATED_SPAN_HEX}",
        },
        # expected_resp_headers
        {},
    ),
    (
        # extra_config
        {
            "NOTIFY_SPAN_ID_HEADER": "barrels-and-boxes",
            "NOTIFY_SPAN_ID_ALT_HEADERS": ("Bloomusalem",),
        },
        # extra_req_headers
        (
            (
                "bloomusalem",  # also checking header case-insensitivity here
                "huge-pork-kidney",
            ),
        ),
        # expected_span_id
        "huge-pork-kidney",
        # expected_parent_span_id
        None,
        # expect_span_random_call_self
        False,
        # expected_onwards_req_headers
        {
            "X-B3-ParentSpanId": "huge-pork-kidney",
            "barrels-and-boxes": _GENERATED_SPAN_HEX,
        },
        # expected_resp_headers
        {
            "barrels-and-boxes": "huge-pork-kidney",
        },
    ),
    (
        # extra_config
        {
            "NOTIFY_PARENT_SPAN_ID_HEADER": "Potato-Preservative",
            "NOTIFY_PARENT_SPAN_ID_ALT_HEADERS": ("X-WANDERING-SOAP",),
        },
        # extra_req_headers
        (
            (
                "POTATO-PRESERVATIVE",  # also checking header case-insensitivity here
                "Plage and Pestilence",
            ),
            (
                "X-WANDERING-SOAP",  # should be ignored in favour of POTATO-PRESERVATIVE's value
                "Flower of the Bath",
            ),
            (
                "X-B3-SpanId",
                "colossal-edifice",
            ),
        ),
        # expected_span_id
        "colossal-edifice",
        # expected_parent_span_id
        "Plage and Pestilence",
        # expect_span_random_call_self
        False,
        # expected_onwards_req_headers
        {
            "Potato-Preservative": "colossal-edifice",
            "X-B3-SpanId": _GENERATED_SPAN_HEX,
        },
        # expected_resp_headers
        {
            "X-B3-SpanId": "colossal-edifice",
        },
    ),
)

_param_combinations = tuple(
    # to prove that the behaviour of trace_id, span_id and parent_span_id is independent, we use the cartesian product
    # of all sets of parameters to test every possible combination of scenarios we've provided...
    (
        # extra_config
        dict(chain(t_extra_config.items(), s_extra_config.items())),
        # extra_req_headers
        tuple(chain(t_extra_req_headers, s_extra_req_headers)),
        expected_trace_id,
        expect_trace_random_call,
        expected_span_id,
        expected_parent_span_id,
        expect_span_random_call_self,  # whether to expect a random call caused by request generating its own span_id
        # expected_onwards_req_headers
        dict(
            chain(
                t_expected_onwards_req_headers.items(),
                s_expected_onwards_req_headers.items(),
            )
        ),
        # expected_resp_headers
        dict(
            chain(
                t_expected_resp_headers.items(),
                s_expected_resp_headers.items(),
            )
        ),
    )
    for (
        t_extra_config,
        t_extra_req_headers,
        expected_trace_id,
        expect_trace_random_call,
        t_expected_onwards_req_headers,
        t_expected_resp_headers,
    ), (
        s_extra_config,
        s_extra_req_headers,
        expected_span_id,
        expected_parent_span_id,
        expect_span_random_call_self,
        s_expected_onwards_req_headers,
        s_expected_resp_headers,
    ) in product(
        _trace_id_related_params,
        _span_id_related_params,
    )
)


@pytest.mark.parametrize(
    (
        "extra_config",
        "extra_req_headers",
        "expected_trace_id",
        "expect_trace_random_call",
        "expected_span_id",
        "expected_parent_span_id",
        "expect_span_random_call_self",
        "expected_onwards_req_headers",
        "expected_resp_headers",
    ),
    _param_combinations,
    ids=_abbreviate_id,
)
@mock.patch.object(request_helper.NotifyRequest, "_traceid_random", autospec=True)
@mock.patch.object(request_helper.NotifyRequest, "_spanid_random", autospec=True)
def test_request_header(
    spanid_random_mock,
    traceid_random_mock,
    extra_config,
    extra_req_headers,
    expected_trace_id,
    expect_trace_random_call,
    expected_span_id,
    expected_parent_span_id,
    expect_span_random_call_self,
    expected_onwards_req_headers,
    expected_resp_headers,  # unused here
):
    app = Flask(__name__)
    app.config.update(extra_config)
    request_helper.init_app(app)

    traceid_random_mock.randrange.return_value = _GENERATED_TRACE_VALUE
    spanid_random_mock.randrange.return_value = _GENERATED_SPAN_VALUE

    with app.test_request_context(headers=extra_req_headers):
        assert request.request_id == request.trace_id == expected_trace_id
        assert request.span_id == expected_span_id
        assert request.parent_span_id == expected_parent_span_id
        assert request.get_onwards_request_headers() == expected_onwards_req_headers

    assert traceid_random_mock.randrange.mock_calls == [] if not expect_trace_random_call else [mock.call(1 << 128)]
    assert spanid_random_mock.randrange.mock_calls == [mock.call(1 << 64)] * (2 if expect_span_random_call_self else 1)


@mock.patch.object(request_helper.NotifyRequest, "_traceid_random", autospec=True)
@mock.patch.object(request_helper.NotifyRequest, "_spanid_random", autospec=True)
def test_request_header_zero_padded(
    spanid_random_mock,
    traceid_random_mock,
):
    app = Flask(__name__)
    request_helper.init_app(app)

    traceid_random_mock.randrange.return_value = 0xBEEF
    spanid_random_mock.randrange.return_value = 0xA

    with app.test_request_context():
        assert request.request_id == request.trace_id == "0000000000000000000000000000beef"
        assert request.span_id == "self-000000000000000a"
        assert request.get_onwards_request_headers() == {
            "X-B3-TraceId": "0000000000000000000000000000beef",
            "X-B3-SpanId": "000000000000000a",
            "X-B3-ParentSpanId": "self-000000000000000a",
        }

    assert traceid_random_mock.randrange.mock_calls == [mock.call(1 << 128)]
    assert spanid_random_mock.randrange.mock_calls == [mock.call(1 << 64), mock.call(1 << 64)]


@pytest.mark.parametrize(
    (
        "extra_config",
        "extra_req_headers",
        "expected_trace_id",
        "expect_trace_random_call",
        "expected_span_id",
        "expected_parent_span_id",
        "expect_span_random_call_self",
        "expected_onwards_req_headers",
        "expected_resp_headers",
    ),
    _param_combinations,
    ids=_abbreviate_id,
)
@mock.patch.object(request_helper.NotifyRequest, "_traceid_random", autospec=True)
@mock.patch.object(request_helper.NotifyRequest, "_spanid_random", autospec=True)
def test_response_headers_regular_response(
    spanid_random_mock,
    traceid_random_mock,
    extra_config,
    extra_req_headers,
    expected_trace_id,  # unused here
    expect_trace_random_call,
    expected_span_id,  # unused here
    expected_parent_span_id,  # unused here
    expect_span_random_call_self,
    expected_onwards_req_headers,  # unused here
    expected_resp_headers,
):
    app = Flask(__name__)
    app.config.update(extra_config)
    request_helper.init_app(app)
    client = app.test_client()

    traceid_random_mock.randrange.return_value = _GENERATED_TRACE_VALUE

    with app.app_context():
        response = client.get("/", headers=extra_req_headers)
        # note using these mechanisms we're not able to test for the *absence* of a header
        assert dict(response.headers) == AnySupersetOf(expected_resp_headers)

    assert traceid_random_mock.randrange.mock_calls == [] if not expect_trace_random_call else [mock.call(1 << 128)]
    assert spanid_random_mock.randrange.mock_calls == [] if not expect_span_random_call_self else [mock.call(1 << 64)]


@pytest.mark.parametrize(
    (
        "extra_config",
        "extra_req_headers",
        "expected_trace_id",
        "expect_trace_random_call",
        "expected_span_id",
        "expected_parent_span_id",
        "expect_span_random_call_self",
        "expected_onwards_req_headers",
        "expected_resp_headers",
    ),
    _param_combinations,
    ids=_abbreviate_id,
)
@mock.patch.object(request_helper.NotifyRequest, "_traceid_random", autospec=True)
@mock.patch.object(request_helper.NotifyRequest, "_spanid_random", autospec=True)
def test_response_headers_error_response(
    spanid_random_mock,
    traceid_random_mock,
    extra_config,
    extra_req_headers,
    expected_trace_id,  # unused here
    expect_trace_random_call,
    expected_span_id,  # unused here
    expected_parent_span_id,  # unused here
    expect_span_random_call_self,
    expected_onwards_req_headers,  # unused here
    expected_resp_headers,
):
    app = Flask(__name__)
    app.config.update(extra_config)
    request_helper.init_app(app)
    client = app.test_client()

    traceid_random_mock.randrange.return_value = _GENERATED_TRACE_VALUE

    @app.route("/")
    def error_route():
        raise Exception

    with app.app_context():
        response = client.get("/", headers=extra_req_headers)
        assert response.status_code == 500
        # note using these mechanisms we're not able to test for the *absence* of a header
        assert dict(response.headers) == AnySupersetOf(expected_resp_headers)

    assert traceid_random_mock.randrange.mock_calls == [] if not expect_trace_random_call else [mock.call(1 << 128)]
    assert spanid_random_mock.randrange.mock_calls == [] if not expect_span_random_call_self else [mock.call(1 << 64)]
