"""Tests that application logs actually reach a handler.

Modules across the app log through ``logging.getLogger(__name__)``. Those
loggers propagate to the root logger, so a handler installed only on
``app.logger`` never saw them: their ``info`` calls were discarded outright and
their warnings fell through to Python's ``lastResort`` handler, unformatted.
These tests pin down that a module logger's records now reach the app's handler,
and that they arrive exactly once.
"""

import io
import logging

import pytest

from app import LOG_HANDLER_NAME, create_app
from config import parse_log_level_env
from conftest import TestConfig


@pytest.fixture
def restore_root_logger():
    """Put the root logger back the way the test session had it.

    ``configure_logging`` mutates process-wide logging state, so a test that
    calls it has to undo that or every later test inherits the change.
    """
    root_logger = logging.getLogger()
    original_handlers = list(root_logger.handlers)
    original_level = root_logger.level

    yield

    root_logger.handlers[:] = original_handlers
    root_logger.setLevel(original_level)


def _capture_app_log_output():
    """Point the app's handler at a buffer and return it."""
    for handler in logging.getLogger().handlers:
        if getattr(handler, "name", None) == LOG_HANDLER_NAME:
            handler.stream = io.StringIO()
            return handler.stream
    raise AssertionError(f"no handler named {LOG_HANDLER_NAME!r} on the root logger")


class LoggingTestConfig(TestConfig):
    LOG_LEVEL = logging.INFO


class TestModuleLoggersReachTheHandler:
    def test_module_logger_info_is_emitted(self, restore_root_logger):
        """The bug this fixes: logger.info from a module went nowhere."""
        create_app(LoggingTestConfig)
        stream = _capture_app_log_output()

        logging.getLogger("app.services.pretend_service").info("service did a thing")

        assert "service did a thing" in stream.getvalue()

    def test_logger_name_appears_in_the_output(self, restore_root_logger):
        """A line is only useful if it says where it came from."""
        create_app(LoggingTestConfig)
        stream = _capture_app_log_output()

        logging.getLogger("app.services.pretend_service").warning("careful")

        assert "app.services.pretend_service" in stream.getvalue()

    def test_app_logger_is_emitted_exactly_once(self, restore_root_logger):
        """app.logger propagates to the root handler and must not double up."""
        app = create_app(LoggingTestConfig)
        stream = _capture_app_log_output()

        app.logger.info("just the once")

        assert stream.getvalue().count("just the once") == 1

    def test_creating_the_app_twice_leaves_one_handler(self, restore_root_logger):
        """The test suite builds several apps; handlers must not accumulate."""
        create_app(LoggingTestConfig)
        create_app(LoggingTestConfig)

        matching = [
            handler
            for handler in logging.getLogger().handlers
            if getattr(handler, "name", None) == LOG_HANDLER_NAME
        ]
        assert len(matching) == 1

    def test_below_the_configured_level_nothing_is_emitted(self, restore_root_logger):
        class QuietConfig(TestConfig):
            LOG_LEVEL = logging.WARNING

        create_app(QuietConfig)
        stream = _capture_app_log_output()

        logging.getLogger("app.services.pretend_service").info("too chatty")

        assert stream.getvalue() == ""

    def test_noisy_libraries_are_pinned_to_warning(self, restore_root_logger):
        """Turning the app down to DEBUG must not drown it in botocore."""

        class VerboseConfig(TestConfig):
            LOG_LEVEL = logging.DEBUG

        create_app(VerboseConfig)

        assert logging.getLogger("botocore").getEffectiveLevel() == logging.WARNING


class TestParseLogLevelEnv:
    def test_level_name_is_resolved(self):
        assert parse_log_level_env("DEBUG", logging.INFO) == logging.DEBUG

    def test_level_name_is_case_insensitive(self):
        assert parse_log_level_env("warning", logging.INFO) == logging.WARNING

    def test_numeric_level_is_accepted(self):
        assert parse_log_level_env("30", logging.INFO) == logging.WARNING

    def test_unset_falls_back_to_the_default(self):
        assert parse_log_level_env(None, logging.INFO) == logging.INFO
        assert parse_log_level_env("   ", logging.INFO) == logging.INFO

    def test_unrecognized_value_falls_back_rather_than_raising(self):
        """A typo in a deploy variable should not stop the app from booting."""
        assert parse_log_level_env("VERBOSE", logging.INFO) == logging.INFO
