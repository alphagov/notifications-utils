import logging

import pytest
import requests_mock
from filelock import FileLock, Timeout
from flask import Flask

from notifications_utils import request_helper
from notifications_utils.clients.redis.redis_client import RedisClient


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
def celery_app():
    app = Flask(__name__)
    app.config["CELERY"] = {"broker_url": "foo"}
    app.config["NOTIFY_TRACE_ID_HEADER"] = "Ex-Notify-Request-Id"
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


@pytest.fixture(scope="function")
def redis_client_with_live_instance(app, tmp_path_factory):
    root_tmp_dir = tmp_path_factory.getbasetemp().parent
    redis_lock_file = root_tmp_dir / "redis_lock"
    app.config["REDIS_ENABLED"] = True
    app.config["REDIS_URL"] = "redis://localhost:6999/0"
    lock = FileLock(str(redis_lock_file) + ".lock")
    try:
        with lock.acquire(timeout=10):
            redis_client = RedisClient()
            redis_client.init_app(app)
            redis_client.redis_store.flushall()
            return redis_client
    except Timeout as e:
        raise Exception(f"Timeout while waiting for redis lock. Detail: {e}") from e
