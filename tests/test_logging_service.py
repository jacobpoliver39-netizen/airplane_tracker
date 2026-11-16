import io
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pytest

from logging_service import DailyFileHandler, LoggingService


@pytest.fixture(autouse=True)
def reset_logging_service():
    """Keep logging configuration isolated between tests."""
    original_level = logging.getLogger().level
    LoggingService.reset()

    yield

    LoggingService.reset()
    logging.getLogger().setLevel(original_level)


def test_initialize_returns_same_instance(tmp_path):
    first = LoggingService.initialize(log_dir=tmp_path)
    second = LoggingService.initialize(log_dir=tmp_path)

    assert first is second
    assert LoggingService.get_instance() is first


def test_direct_construction_is_rejected():
    with pytest.raises(RuntimeError):
        LoggingService()


def test_concurrent_initialization_returns_one_instance(tmp_path):
    barrier = threading.Barrier(8)

    def initialize():
        barrier.wait()
        return LoggingService.initialize(log_dir=tmp_path)

    with ThreadPoolExecutor(max_workers=8) as executor:
        instances = list(executor.map(lambda _: initialize(), range(8)))

    assert all(instance is instances[0] for instance in instances)


def test_file_handler_records_info_and_above(tmp_path):
    service = LoggingService.initialize(
        log_dir=tmp_path,
        log_date=date(2026, 11, 10),
    )

    logger = logging.getLogger("test.file_output")
    logger.info("information message")
    logger.warning("warning message")
    logger.error("error message")

    LoggingService.close()

    contents = service._log_path.read_text(encoding="utf-8")

    assert "information message" in contents
    assert "warning message" in contents
    assert "error message" in contents
    assert "debug message" not in contents


def test_console_handler_records_warning_and_above(tmp_path):
    console = io.StringIO()

    LoggingService.initialize(
        log_dir=tmp_path,
        console_stream=console,
    )

    logger = logging.getLogger("test.console_output")
    logger.debug("debug message")
    logger.info("information message")
    logger.warning("warning message")
    logger.error("error message")

    output = console.getvalue()

    assert "warning message" in output
    assert "error message" in output
    assert "information message" not in output
    assert "debug message" not in output


def test_reset_allows_new_configuration(tmp_path):
    first = LoggingService.initialize(log_dir=tmp_path / "first")
    LoggingService.reset()

    second = LoggingService.initialize(log_dir=tmp_path / "second")

    assert first is not second
    assert first._log_path.parent != second._log_path.parent


def test_reset_closes_handlers(tmp_path):
    service = LoggingService.initialize(log_dir=tmp_path)
    handlers = list(service._handlers)

    file_handler = next(
        handler for handler in handlers
        if isinstance(handler, logging.FileHandler)
    )
    console_handler = next(
        handler for handler in handlers
        if isinstance(handler, logging.StreamHandler)
        and not isinstance(handler, logging.FileHandler)
    )

    LoggingService.reset()

    assert service._handlers == []
    assert all(handler not in logging.getLogger().handlers for handler in handlers)

    # The service owns and closes the file.
    assert file_handler.stream is None

    # The service closes the handler, but not its external stream.
    assert console_handler._closed

def test_daily_file_handler_switches_file_when_date_changes(tmp_path):
    current = {"date": date(2026, 11, 10)}
    handler = DailyFileHandler(tmp_path, lambda: current["date"])
    logger = logging.getLogger("test.daily_rotation")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    try:
        logger.info("first day")
        current["date"] = date(2026, 11, 11)
        logger.info("second day")
    finally:
        logger.removeHandler(handler)
        handler.close()

    first = (tmp_path / "jacobsky_2026-11-10.log").read_text(encoding="utf-8")
    second = (tmp_path / "jacobsky_2026-11-11.log").read_text(encoding="utf-8")

    assert "first day" in first and "second day" not in first
    assert "second day" in second


def test_close_allows_reinitialization(tmp_path):
    first = LoggingService.initialize(log_dir=tmp_path)
    LoggingService.close()

    second = LoggingService.initialize(log_dir=tmp_path)

    assert first is not second
    assert second._handlers
