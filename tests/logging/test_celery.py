import json
import os
import pathlib
import subprocess
import warnings
from unittest.mock import MagicMock, patch

import pytest

from notifications_utils.logging.celery import set_up_logging, setup_logging_connect


def test_set_up_logging_success():
    """Test that set_up_logging correctly overrides warnings.showwarning."""
    logger = MagicMock()
    set_up_logging(logger)

    # Assert that warnings.showwarning is overridden
    assert warnings.showwarning != warnings._showwarning_orig

    # Simulate a warning and check if it logs correctly
    warnings.showwarning("Test message", UserWarning, "test_file.py", 42)
    logger.warning.assert_called_once_with(
        "Test message",
        {
            "level": "WARNING",
            "message": "Test message",
            "category": "UserWarning",
            "filename": "test_file.py",
            "lineno": 42,
        },
    )


def test_set_up_logging_missing_logger():
    logger = None

    with pytest.raises(AttributeError, match="The provided logger object is invalid."):
        set_up_logging(logger)


@patch("notifications_utils.logging.celery.dictConfig")
def test_setup_logging_connect_success(mock_dict_config):
    """Test that setup_logging_connect successfully configures logging."""
    setup_logging_connect()

    # Assert that dictConfig was called
    mock_dict_config.assert_called_once()


def test_celery_dummy_logs(tmp_path):
    command = [
        "celery",
        "--quiet",
        "-A",
        "dummy_celery_app",
        "worker",
        "--loglevel=INFO",
    ]

    # Set the environment variable
    env = os.environ.copy()
    env["CELERY_LOG_LEVEL"] = "INFO"

    # assemble an example celery app directory, able to access notifications_utils
    # via a cwd link
    (tmp_path / "notifications_utils").symlink_to(pathlib.Path(__file__).parent.parent.parent / "notifications_utils")
    (tmp_path / "dummy_celery_app.py").symlink_to(pathlib.Path(__file__).parent / "dummy_celery_app.py")

    try:
        # Start the Celery worker process
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            cwd=tmp_path,
        )

        stdout, stderr = process.communicate(timeout=10)
        logs = stdout + stderr

        expected_messages = [
            "No hostname was supplied. Reverting to default 'localhost'",
            "Connected to memory://localhost//",
            "Task dummy_celery_app.test_task",
        ]

        # Parse the logs as JSON and check the messages field contains the expected messages
        for log_line in logs.splitlines():
            try:
                log_json = json.loads(log_line)  # Ensure the line is valid JSON
                log_message = log_json.get("message", "")
                for message in expected_messages:
                    if message in log_message:
                        expected_messages.remove(message)
            except json.JSONDecodeError:
                continue

        # Assert that all expected messages were found
        assert not expected_messages, f"Expected messages not found in logs: {expected_messages}. Logs are:\n{logs}"

    except subprocess.TimeoutExpired:
        pytest.fail("The Celery process timed out. Check for potential deadlocks or excessive output.")
    except FileNotFoundError:
        pytest.fail("Celery command not found. Ensure Celery is installed and in PATH.")
    except Exception as e:
        pytest.fail(f"Unexpected error occurred: {e}")
