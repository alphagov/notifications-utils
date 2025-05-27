import json
import os
import pathlib
import subprocess
from unittest.mock import patch

import pytest

from notifications_utils.logging.celery import setup_logging_connect


class Config:
    CELERY_WORKER_LOG_LEVEL = "CRITICAL"
    CELERY_BEAT_LOG_LEVEL = "INFO"

    def get(self, key, default=None):
        return getattr(self, key, default)


@patch("notifications_utils.logging.celery.dictConfig")
@patch("notifications_utils.logging.celery.config", Config())
def test_setup_logging_connect_success(mock_dict_config):
    """Test that setup_logging_connect successfully configures logging."""

    setup_logging_connect()

    # Assert that dictConfig was called
    mock_dict_config.assert_called_once()


def assert_command_has_outputs(tmp_path, command, filename, expected_messages, unexpected_messages=None, env=None):
    if unexpected_messages is None:
        unexpected_messages = []

    (tmp_path / "notifications_utils").symlink_to(pathlib.Path(__file__).parent.parent.parent / "notifications_utils")
    (tmp_path / filename).symlink_to(pathlib.Path(__file__).parent / filename)

    try:
        # Start the Celery worker process
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=tmp_path,
            env=env,
        )

        stdout, stderr = process.communicate(timeout=10)
        logs = stdout + stderr

        # Parse the logs as JSON and check the messages field contains the expected messages
        for log_line in logs.splitlines():
            try:
                log_json = json.loads(log_line)  # Ensure the line is valid JSON
                log_message = log_json.get("message", "")
                for message in expected_messages:
                    if message in log_message:
                        expected_messages.remove(message)
                for bad_message in unexpected_messages:
                    assert bad_message not in log_message, (
                        f"Unexpected message found in logs: '{bad_message}'. Logs are:\n{logs}"
                    )
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


@pytest.mark.slow
def test_celery_dummy_logs(tmp_path):
    command = ["celery", "--quiet", "-A", "dummy_celery_app", "worker", "-B"]

    expected_messages = [
        "Connected to filesystem://localhost//",
        "beat: Starting...",
        "Task test_task",
        "Scheduler: Sending due task test-task",
        "beat: Shutting down...",
    ]

    env = os.environ.copy()
    env["CELERY_WORKER_LOG_LEVEL"] = "INFO"
    env["CELERY_BEAT_LOG_LEVEL"] = "INFO"
    assert_command_has_outputs(tmp_path, command, "dummy_celery_app.py", expected_messages, env=env)


@pytest.mark.slow
def test_celery_worker_logs_absent(tmp_path):
    command = [
        "celery",
        "--quiet",
        "-A",
        "dummy_celery_app",
        "worker",
        "-B",
    ]

    expected_messages = [
        "beat: Starting...",
        "Scheduler: Sending due task test-task",
        "beat: Shutting down...",
    ]

    unexpected_messages = ["Connected to filesystem://localhost//", "Task test_task"]

    env = os.environ.copy()
    # test we aren't leaking celery worker logs when set to CRITICAL. They could contain PII
    # or other sensitive data.
    env["CELERY_WORKER_LOG_LEVEL"] = "CRITICAL"
    env["CELERY_BEAT_LOG_LEVEL"] = "INFO"

    assert_command_has_outputs(
        tmp_path, command, "dummy_celery_app.py", expected_messages, unexpected_messages, env=env
    )
