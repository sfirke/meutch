"""Tests that a module logger's records reach the app's handler, exactly once."""

import io
import logging

import pytest

from app import LOG_HANDLER_NAME, NOISY_LIBRARY_LOGGERS, create_app
from config import parse_log_level_env
from conftest import TestConfig


@pytest.fixture
def restore_root_logger():
    """Put process-wide logging state back the way the test session had it.

    ``configure_logging`` mutates the root logger, the ``app`` logger (shared by
    every app built in this process) and the pinned library loggers.
    """
    root_logger = logging.getLogger()
    original_handlers = list(root_logger.handlers)
    original_level = root_logger.level
    other_loggers = ("app", *NOISY_LIBRARY_LOGGERS)
    original_levels = {name: logging.getLogger(name).level for name in other_loggers}

    yield

    root_logger.handlers[:] = original_handlers
    root_logger.setLevel(original_level)
    for name, level in original_levels.items():
        logging.getLogger(name).setLevel(level)


def _app_log_handlers():
    return [h for h in logging.getLogger().handlers if h.name == LOG_HANDLER_NAME]


def _capture_app_log_output():
    """Point the app's handler at a buffer and return it."""
    handlers = _app_log_handlers()
    assert handlers, f"no handler named {LOG_HANDLER_NAME!r} on the root logger"
    handlers[0].stream = io.StringIO()
    return handlers[0].stream


class LoggingTestConfig(TestConfig):
    LOG_LEVEL = logging.INFO


class TestModuleLoggersReachTheHandler:
    def test_module_logger_info_is_emitted(self, restore_root_logger):
        create_app(LoggingTestConfig)
        stream = _capture_app_log_output()

        logging.getLogger("app.services.pretend_service").info("service did a thing")

        assert "service did a thing" in stream.getvalue()

    def test_logger_name_appears_in_the_output(self, restore_root_logger):
        create_app(LoggingTestConfig)
        stream = _capture_app_log_output()

        logging.getLogger("app.services.pretend_service").warning("careful")

        assert "app.services.pretend_service" in stream.getvalue()

    def test_app_logger_output_names_the_calling_module(self, restore_root_logger):
        """Every app.logger call shares the name "app"; the module says which file."""
        app = create_app(LoggingTestConfig)
        stream = _capture_app_log_output()

        app.logger.warning("from a view")

        assert "app [test_logging_config]" in stream.getvalue()

    def test_app_logger_is_emitted_exactly_once(self, restore_root_logger):
        app = create_app(LoggingTestConfig)
        stream = _capture_app_log_output()

        app.logger.info("just the once")

        assert stream.getvalue().count("just the once") == 1

    def test_creating_the_app_twice_leaves_one_handler(self, restore_root_logger):
        create_app(LoggingTestConfig)
        create_app(LoggingTestConfig)

        assert len(_app_log_handlers()) == 1

    def test_below_the_configured_level_nothing_is_emitted(self, restore_root_logger):
        class QuietConfig(TestConfig):
            LOG_LEVEL = logging.WARNING

        create_app(QuietConfig)
        stream = _capture_app_log_output()

        logging.getLogger("app.services.pretend_service").info("too chatty")

        assert stream.getvalue() == ""

    def test_one_logger_can_be_turned_up_past_the_configured_level(self, restore_root_logger):
        create_app(LoggingTestConfig)
        stream = _capture_app_log_output()

        chatty = logging.getLogger("app.services.pretend_service")
        chatty.setLevel(logging.DEBUG)
        chatty.debug("detail")

        assert "detail" in stream.getvalue()

    def test_noisy_libraries_are_pinned_to_warning(self, restore_root_logger):
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
        assert parse_log_level_env("VERBOSE", logging.INFO) == logging.INFO
        assert parse_log_level_env("²", logging.INFO) == logging.INFO

    def test_zero_and_notset_fall_back_to_the_default(self):
        """Level 0 on the root logger would mean "log everything"."""
        assert parse_log_level_env("0", logging.INFO) == logging.INFO
        assert parse_log_level_env("NOTSET", logging.INFO) == logging.INFO
