import inspect
import logging
import uuid

import pytest
from celery import Task
from flask import g
from freezegun import freeze_time

from notifications_utils.celery import NotifyCelery


@pytest.fixture
def notify_celery(celery_app):
    celery = NotifyCelery()
    celery.init_app(celery_app)
    return celery


@pytest.fixture
def celery_task(notify_celery):
    @notify_celery.task(name=uuid.uuid4(), base=notify_celery.task_cls)
    def test_task(delivery_info=None):
        pass

    return test_task


@pytest.fixture
def celery_task_early_debug(notify_celery):
    @notify_celery.task(name=uuid.uuid4(), base=notify_celery.task_cls, early_log_level=logging.DEBUG)
    def test_task(delivery_info=None):
        pass

    return test_task


@pytest.fixture
def async_task(celery_task):
    celery_task.push_request(delivery_info={"routing_key": "test-queue"}, id=1234)
    yield celery_task
    celery_task.pop_request()


@pytest.fixture
def async_task_early_debug(celery_task_early_debug):
    celery_task_early_debug.push_request(delivery_info={"routing_key": "test-queue"}, id=1234)
    yield celery_task_early_debug
    celery_task_early_debug.pop_request()


@pytest.fixture
def request_id_task(celery_task):
    # Note that each header is a direct attribute of the
    # task context (aka "request").
    celery_task.push_request(notify_request_id="1234", id=1234)
    yield celery_task
    celery_task.pop_request()


def test_success_should_log_and_add_metrics(celery_app, async_task, caplog):
    statsd_mock = celery_app.statsd_client.timing
    otel_mock = celery_app.otel_client.record

    with freeze_time() as frozen, caplog.at_level(logging.INFO):
        async_task()
        frozen.tick(5)

        async_task.on_success(retval=None, task_id=1234, args=[], kwargs={})

    statsd_mock.assert_called_once_with(f"celery.test-queue.{async_task.name}.success", 5.0)
    otel_mock.assert_called_once_with(
        "celery_task_success_duration_seconds",
        value=5.0,
        attributes={"task": async_task.name, "queue": "test-queue"},
        description="Celery task success duration in seconds",
        unit="s",
    )
    assert f"Celery task {async_task.name} (queue: test-queue) started" in caplog.messages
    assert f"Celery task {async_task.name} (queue: test-queue) took 5.0000" in caplog.messages


def test_success_no_early_log(celery_app, async_task_early_debug, caplog):
    statsd_mock = celery_app.statsd_client.timing
    otel_mock = celery_app.otel_client.record

    with freeze_time() as frozen, caplog.at_level(logging.INFO):
        async_task_early_debug()
        frozen.tick(5)

        async_task_early_debug.on_success(retval=None, task_id=1234, args=[], kwargs={})

    statsd_mock.assert_called_once_with(f"celery.test-queue.{async_task_early_debug.name}.success", 5.0)
    otel_mock.assert_called_once_with(
        "celery_task_success_duration_seconds",
        value=5.0,
        attributes={"task": async_task_early_debug.name, "queue": "test-queue"},
        description="Celery task success duration in seconds",
        unit="s",
    )
    assert f"Celery task {async_task_early_debug.name} (queue: test-queue) started" not in caplog.messages
    assert f"Celery task {async_task_early_debug.name} (queue: test-queue) took 5.0000" in caplog.messages


def test_success_queue_when_applied_synchronously(celery_app, celery_task, caplog):
    statsd_mock = celery_app.statsd_client.timing
    otel_mock = celery_app.otel_client.record

    with freeze_time() as frozen, caplog.at_level(logging.INFO):
        celery_task()
        frozen.tick(5)

        celery_task.on_success(retval=None, task_id=1234, args=[], kwargs={})

    statsd_mock.assert_called_once_with(f"celery.none.{celery_task.name}.success", 5.0)
    otel_mock.assert_called_once_with(
        "celery_task_success_duration_seconds",
        value=5.0,
        attributes={"task": celery_task.name, "queue": "none"},
        description="Celery task success duration in seconds",
        unit="s",
    )
    assert f"Celery task {celery_task.name} (queue: none) started" not in caplog.messages
    assert f"Celery task {celery_task.name} (queue: none) took 5.0000" in caplog.messages


def test_retry_should_log_and_add_metrics(celery_app, async_task, caplog):
    statsd_mock = celery_app.statsd_client.timing
    otel_mock = celery_app.otel_client.record

    with freeze_time() as frozen, caplog.at_level(logging.WARNING):
        async_task()
        frozen.tick(5)

        async_task.on_retry(exc=Exception, task_id="1234", args=[], kwargs={}, einfo=None)

    statsd_mock.assert_called_once_with(f"celery.test-queue.{async_task.name}.retry", 5.0)
    otel_mock.assert_called_once_with(
        "celery_task_retry_duration_seconds",
        value=5.0,
        attributes={"task": async_task.name, "queue": "test-queue"},
        description="Celery task retry duration in seconds",
        unit="s",
    )
    assert f"Celery task {async_task.name} (queue: test-queue) started" not in caplog.messages  # log level too low
    assert f"Celery task {async_task.name} (queue: test-queue) failed for retry after 5.0000" in caplog.messages


def test_retry_queue_when_applied_synchronously(celery_app, celery_task, caplog):
    statsd_mock = celery_app.statsd_client.timing
    otel_mock = celery_app.otel_client.record

    with freeze_time() as frozen, caplog.at_level(logging.WARNING):
        celery_task()
        frozen.tick(5)

        celery_task.on_retry(exc=Exception, task_id="1234", args=[], kwargs={}, einfo=None)

    statsd_mock.assert_called_once_with(f"celery.none.{celery_task.name}.retry", 5.0)
    otel_mock.assert_called_once_with(
        "celery_task_retry_duration_seconds",
        value=5.0,
        attributes={"task": celery_task.name, "queue": "none"},
        description="Celery task retry duration in seconds",
        unit="s",
    )
    assert f"Celery task {celery_task.name} (queue: none) started" not in caplog.messages  # log level too low
    assert f"Celery task {celery_task.name} (queue: none) failed for retry after 5.0000" in caplog.messages


def test_failure_should_log_and_add_metrics(celery_app, async_task, caplog):
    statsd_mock = celery_app.statsd_client.incr
    otel_mock = celery_app.otel_client.incr

    with freeze_time() as frozen, caplog.at_level(logging.INFO):
        async_task()
        frozen.tick(5)

        async_task.on_failure(exc=Exception, task_id=1234, args=[], kwargs={}, einfo=None)

    statsd_mock.assert_called_once_with(f"celery.test-queue.{async_task.name}.failure")
    otel_mock.assert_called_once_with(
        "celery_task_failure_total",
        value=1,
        attributes={"task": async_task.name, "queue": "test-queue"},
        description="Celery task failures",
        unit="1",
    )

    assert f"Celery task {async_task.name} (queue: test-queue) started" in caplog.messages
    assert f"Celery task {async_task.name} (queue: test-queue) failed after 5.0000" in caplog.messages


def test_failure_queue_when_applied_synchronously(celery_app, celery_task, caplog):
    statsd_mock = celery_app.statsd_client.incr
    otel_mock = celery_app.otel_client.incr

    with freeze_time() as frozen, caplog.at_level(logging.ERROR):
        celery_task()
        frozen.tick(5)
        celery_task.on_failure(exc=Exception, task_id=1234, args=[], kwargs={}, einfo=None)

    statsd_mock.assert_called_once_with(f"celery.none.{celery_task.name}.failure")
    otel_mock.assert_called_once_with(
        "celery_task_failure_total",
        value=1,
        attributes={"task": celery_task.name, "queue": "none"},
        description="Celery task failures",
        unit="1",
    )

    assert f"Celery task {celery_task.name} (queue: none) started" not in caplog.messages  # log level too low
    assert f"Celery task {celery_task.name} (queue: none) failed after 5.0000" in caplog.messages


def test_call_exports_request_id_from_headers(mocker, request_id_task):
    g = mocker.patch("notifications_utils.celery.g")
    request_id_task()
    assert g.request_id == "1234"


def test_copes_if_request_id_not_in_headers(mocker, celery_task):
    g = mocker.patch("notifications_utils.celery.g")
    celery_task()
    assert g.request_id is None


def test_injects_celery_task_id_if_no_request_id(mocker, celery_task):
    mocker.patch("celery.app.task.uuid", return_value="my-random-uuid")
    g = mocker.patch("notifications_utils.celery.g")
    celery_task.apply()
    assert g.request_id == "my-random-uuid"


def test_send_task_injects_global_request_id_into_headers(
    mocker,
    notify_celery,
):
    super_apply = mocker.patch("celery.Celery.send_task")
    g.request_id = "1234"
    notify_celery.send_task("some-task")

    super_apply.assert_called_with(
        "some-task",  # name
        None,  # args
        None,  # kwargs
        headers={"notify_request_id": "1234"},  # other kwargs
    )


def test_send_task_injects_request_id_with_existing_headers(
    mocker,
    notify_celery,
):
    super_apply = mocker.patch("celery.Celery.send_task")
    g.request_id = "1234"

    notify_celery.send_task("some-task", None, None, headers={"something": "else"})  # args  # kwargs  # other kwargs

    super_apply.assert_called_with(
        "some-task",  # name
        None,  # args
        None,  # kwargs
        headers={"notify_request_id": "1234", "something": "else"},  # other kwargs
    )


def test_send_task_injects_request_id_with_none_headers(
    mocker,
    notify_celery,
):
    super_apply = mocker.patch("celery.Celery.send_task")
    g.request_id = "1234"

    notify_celery.send_task(
        "some-task",  # name
        None,  # args
        None,  # kwargs
        headers=None,  # other kwargs (task retry set headers to "None")
    )

    super_apply.assert_called_with(
        "some-task",  # name
        None,  # args
        None,  # kwargs
        headers={"notify_request_id": "1234"},  # other kwargs
    )


def test_send_task_injects_id_from_request(
    mocker,
    notify_celery,
    celery_app,
):
    super_apply = mocker.patch("celery.Celery.send_task")
    request_id_header = celery_app.config["NOTIFY_TRACE_ID_HEADER"]
    request_headers = {request_id_header: "1234"}

    with celery_app.test_request_context(headers=request_headers):
        notify_celery.send_task("some-task")

    super_apply.assert_called_with(
        "some-task",  # name
        None,  # args
        None,  # kwargs
        headers={"notify_request_id": "1234"},  # other kwargs
    )


@pytest.mark.parametrize("method, _value", list(inspect.getmembers(Task, predicate=inspect.isfunction)))
def test_method_signatures(celery_app, async_task, method, _value):
    if method == "run":
        return
    assert inspect.signature(getattr(async_task.__class__, method)) == inspect.signature(getattr(Task, method))
