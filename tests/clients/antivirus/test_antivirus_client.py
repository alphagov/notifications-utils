import io

import pytest
import requests

from notifications_utils import request_helper
from notifications_utils.clients.antivirus.antivirus_client import (
    AntivirusClient,
    AntivirusError,
)


@pytest.fixture(scope="function")
def app_antivirus_client(app, mocker):
    client = AntivirusClient(
        api_host="https://antivirus",
        auth_token="test-antivirus-key",
    )
    return app, client


@pytest.mark.parametrize(
    "with_request_helper",
    (
        False,
        True,
    ),
)
def test_scan_document(app_antivirus_client, rmock, mocker, with_request_helper):
    app, antivirus_client = app_antivirus_client

    if with_request_helper:
        mock_gorh = mocker.patch("notifications_utils.request_helper.NotifyRequest.get_onwards_request_headers")
        mock_gorh.return_value = {"some-onwards": "request-headers"}
        request_helper.init_app(app)

    with app.test_request_context():
        document = io.BytesIO(b"filecontents")
        rmock.request(
            "POST",
            "https://antivirus/scan",
            json={"ok": True},
            request_headers={
                "Authorization": "Bearer test-antivirus-key",
                **({"some-onwards": "request-headers"} if with_request_helper else {}),
            },
            status_code=200,
        )

        resp = antivirus_client.scan(document)

    assert resp
    assert "filecontents" in rmock.last_request.text
    assert document.tell() == 0


def test_should_raise_for_status(app_antivirus_client, rmock):
    app, antivirus_client = app_antivirus_client
    with pytest.raises(AntivirusError) as excinfo:
        rmock.request("POST", "https://antivirus/scan", json={"error": "Antivirus error"}, status_code=400)

        antivirus_client.scan(io.BytesIO(b"document"))

    assert excinfo.value.message == "Antivirus error"
    assert excinfo.value.status_code == 400


def test_should_raise_for_connection_errors(app_antivirus_client, rmock):
    app, antivirus_client = app_antivirus_client
    with pytest.raises(AntivirusError) as excinfo:
        rmock.request("POST", "https://antivirus/scan", exc=requests.exceptions.ConnectTimeout)
        antivirus_client.scan(io.BytesIO(b"document"))

    assert excinfo.value.message == "connection error"
    assert excinfo.value.status_code == 503
