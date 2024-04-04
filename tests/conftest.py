import logging

import pytest
import requests_mock
from flask import Flask

from notifications_utils import request_helper


class FakeService:
    id = "1234"


def _create_app(extra_config={}):  # noqa
    flask_app = Flask(__name__)
    flask_app.config.update(extra_config)
    ctx = flask_app.app_context()
    ctx.push()

    yield flask_app

    ctx.pop()


@pytest.fixture
def app():
    yield from _create_app()


@pytest.fixture
def celery_app(mocker):
    app = Flask(__name__)
    app.config["CELERY"] = {"broker_url": "foo"}
    app.config["NOTIFY_TRACE_ID_HEADER"] = "Ex-Notify-Request-Id"
    app.statsd_client = mocker.Mock()
    request_helper.init_app(app)

    ctx = app.app_context()
    ctx.push()

    yield app
    ctx.pop()


@pytest.fixture
def app_with_mocked_logger(mocker, tmpdir):
    """Patch `create_logger` to return a mock logger that is made accessible on `app.logger`"""
    mocker.patch(
        "flask.sansio.app.create_logger",
        return_value=mocker.Mock(spec=logging.Logger("flask.app"), handlers=[]),
    )
    yield from _create_app()


@pytest.fixture(scope="session")
def sample_service():
    return FakeService()


@pytest.fixture
def rmock():
    with requests_mock.mock() as rmock:
        yield rmock
