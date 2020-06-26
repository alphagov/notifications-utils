import logging as builtin_logging
import logging.handlers as builtin_logging_handlers
import uuid

from notifications_utils import logging


def test_should_build_complete_log_line():
    service_id = uuid.uuid4()
    extra_fields = {
        'method': "method",
        'url': "url",
        'status': 200,
        'time_taken': "time_taken",
        'service_id': service_id
    }
    assert "{service_id} method url 200 time_taken".format(
        service_id=str(service_id)) == logging.build_log_line(extra_fields)


def test_should_build_complete_log_line_ignoring_missing_fields():
    service_id = uuid.uuid4()
    extra_fields = {
        'method': "method",
        'status': 200,
        'time_taken': "time_taken",
        'service_id': service_id
    }
    assert "{service_id} method 200 time_taken".format(
        service_id=str(service_id)) == logging.build_log_line(extra_fields)


def test_should_build_log_line_without_service_id():
    extra_fields = {
        'method': "method",
        'url': "url",
        'status': 200,
        'time_taken': "time_taken"
    }
    assert "method url 200 time_taken" == logging.build_log_line(extra_fields)


def test_should_build_log_line_without_service_id_or_time_taken():
    extra_fields = {
        'method': "method",
        'url': "url",
        'status': 200
    }
    assert "method url 200" == logging.build_log_line(extra_fields)


def test_get_handlers_sets_up_logging_appropriately_with_debug(tmpdir):
    class App:
        config = {
            'NOTIFY_LOG_PATH': str(tmpdir / 'foo'),
            'NOTIFY_APP_NAME': 'bar',
            'NOTIFY_LOG_LEVEL': 'ERROR'
        }
        debug = True

    app = App()

    handlers = logging.get_handlers(app)

    assert len(handlers) == 1
    assert type(handlers[0]) == builtin_logging.StreamHandler
    assert type(handlers[0].formatter) == logging.CustomLogFormatter
    assert not (tmpdir / 'foo').exists()


def test_get_handlers_sets_up_logging_appropriately_without_debug(tmpdir):
    class App:
        config = {
            # make a tempfile called foo
            'NOTIFY_LOG_PATH': str(tmpdir / 'foo'),
            'NOTIFY_APP_NAME': 'bar',
            'NOTIFY_LOG_LEVEL': 'ERROR'
        }
        debug = False

    app = App()

    handlers = logging.get_handlers(app)

    assert len(handlers) == 2
    assert type(handlers[0]) == builtin_logging.StreamHandler
    assert type(handlers[0].formatter) == logging.JSONFormatter

    assert type(handlers[1]) == builtin_logging_handlers.WatchedFileHandler
    assert type(handlers[1].formatter) == logging.JSONFormatter

    dir_contents = tmpdir.listdir()
    assert len(dir_contents) == 1
    assert dir_contents[0].basename == 'foo.json'
