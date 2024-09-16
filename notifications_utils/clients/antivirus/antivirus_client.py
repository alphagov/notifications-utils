import requests
from flask import current_app, request
from flask.ctx import has_request_context


class AntivirusError(Exception):
    def __init__(self, message=None, status_code=None):
        self.message = message
        self.status_code = status_code

    @classmethod
    def from_exception(cls, e):
        try:
            message = e.response.json()["error"]
            status_code = e.response.status_code
        except (TypeError, ValueError, AttributeError, KeyError):
            message = "connection error"
            status_code = 503

        return cls(message, status_code)


class AntivirusClient:
    """
    A client for the antivirus API

    This class is not thread-safe.
    """

    def __init__(self, api_host=None, auth_token=None):
        self.api_host = api_host
        self.auth_token = auth_token
        self.requests_session = requests.Session()

    def scan(self, document_stream):
        headers = {"Authorization": f"Bearer {self.auth_token}"}
        if has_request_context() and hasattr(request, "get_onwards_request_headers"):
            headers.update(request.get_onwards_request_headers())

        try:
            response = self.requests_session.post(
                f"{self.api_host}/scan",
                headers=headers,
                files={"document": document_stream},
            )

            response.raise_for_status()

        except requests.RequestException as e:
            error = AntivirusError.from_exception(e)
            current_app.logger.warning("Notify Antivirus API request failed with error: %s", error.message)

            raise error from e
        finally:
            document_stream.seek(0)

        return response.json()["ok"]
