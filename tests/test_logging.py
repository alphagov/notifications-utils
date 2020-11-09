import json
import logging as builtin_logging
import logging.handlers as builtin_logging_handlers

from notifications_utils import logging


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


def test_base_json_formatter_contains_service_id(tmpdir):
    record = builtin_logging.LogRecord(name="log thing", level="info",
                                       pathname="path", lineno=123, msg='message to log',
                                       exc_info=None, args=None)

    service_id_filter = logging.ServiceIdFilter()
    assert json.loads(logging.BaseJSONFormatter().format(record))['message'] == 'message to log'
    assert service_id_filter.filter(record).service_id == "no-service-id"
