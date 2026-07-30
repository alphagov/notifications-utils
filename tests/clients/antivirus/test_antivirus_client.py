import io

import pytest
import requests
from werkzeug.datastructures import FileStorage

from notifications_utils import request_helper
from notifications_utils.clients.antivirus.antivirus_client import (
    AntivirusClient,
    AntivirusError,
    _multipart_file,
)

# Who calls scan() in production:
# - notifications-admin: user picks a file in the browser (PDF on letter templates, logos, etc.)
# - document-download-api: file content arrives as raw bytes inside a JSON API request


@pytest.fixture(scope="function")
def app_antivirus_client(app, mocker):
    client = AntivirusClient(
        api_host="https://antivirus",
        auth_token="test-antivirus-key",
    )
    return app, client


def _register_scan_ok(rmock):
    rmock.request(
        "POST",
        "https://antivirus/scan",
        json={"ok": True},
        request_headers={"Authorization": "Bearer test-antivirus-key"},
        status_code=200,
    )


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


def test_scan_document_accepts_werkzeug_file_storage(app_antivirus_client, rmock):
    """Same shape as notifications-admin when someone uploads a file through a form (e.g. attach PDF to a letter)."""
    app, antivirus_client = app_antivirus_client

    with app.test_request_context():
        # Stands in for a file the user chose in admin (name + contents + type).
        document = FileStorage(
            stream=io.BytesIO(b"filecontents"),
            filename="attachment.pdf",
            content_type="application/pdf",
        )
        _register_scan_ok(rmock)

        resp = antivirus_client.scan(document)

    assert resp
    assert "filecontents" in rmock.last_request.text
    assert document.tell() == 0


def test_scan_document_accepts_raw_bytes(app_antivirus_client, rmock):
    """Same shape as document-download-api: file content as plain bytes, not a browser upload object."""
    app, antivirus_client = app_antivirus_client

    with app.test_request_context():
        document = b"filecontents"
        assert not hasattr(document, "seek")
        _register_scan_ok(rmock)

        resp = antivirus_client.scan(document)

    assert resp
    assert "filecontents" in rmock.last_request.text


def test_multipart_file_unwraps_file_storage_for_requests():
    """Admin uploads (letter attach-pages, Sentry NOTIFICATIONS-ADMIN-QE) go to requests as the wrapped stream."""
    stream = io.BytesIO(b"filecontents")
    document = FileStorage(stream=stream, filename="attachment.pdf", content_type="application/pdf")

    assert _multipart_file(document) is stream


def test_multipart_file_leaves_bytes_unchanged():
    """document-download-api sends bytes; we should not wrap or change them."""
    document = b"filecontents"
    assert _multipart_file(document) is document


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
