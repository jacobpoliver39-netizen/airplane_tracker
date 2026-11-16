import logging
import os
import sys
import threading
from datetime import date
from pathlib import Path
from typing import TextIO


class DailyFileHandler(logging.FileHandler):
    """
    File handler that writes to logs/jacobsky_YYYY-MM-DD.log and switches
    to a new file when the date changes, so a long-running server does
    not keep writing to the file of the day it started.
    """

    def __init__(self, directory, date_provider=date.today):
        self._directory = Path(directory)
        self._date_provider = date_provider
        self._current_date = date_provider()

        super().__init__(
            self._path_for(self._current_date),
            encoding="utf-8",
        )

    @property
    def path(self):
        return Path(self.baseFilename)

    def _path_for(self, log_date):
        return self._directory / f"jacobsky_{log_date:%Y-%m-%d}.log"

    def emit(self, record):
        # handle() already holds this handler's lock while calling emit().
        today = self._date_provider()

        if today != self._current_date:
            if self.stream is not None:
                self.stream.close()
                self.stream = None

            self._current_date = today
            self.baseFilename = os.path.abspath(self._path_for(today))

        super().emit(record)


class LoggingService:
    """Thread-safe, process-wide logging configuration for JacobSky."""

    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        raise RuntimeError(
            "Use LoggingService.initialize() to create the Singleton"
        )

    @classmethod
    def initialize(
        cls,
        log_dir="logs",
        log_date=None,
        console_stream: TextIO = None,
    ):
        """
        Create the shared logging service, or return the existing one.

        log_date pins the log file to one date (used by tests); by
        default the file follows the current date.
        """
        with cls._lock:
            if cls._instance is not None:
                return cls._instance

            service = object.__new__(cls)

            directory = Path(log_dir)
            directory.mkdir(parents=True, exist_ok=True)

            date_provider = (
                date.today if log_date is None else (lambda: log_date)
            )

            formatter = logging.Formatter(
                "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
            )

            file_handler = DailyFileHandler(directory, date_provider)
            file_handler.setLevel(logging.INFO)
            file_handler.setFormatter(formatter)

            console_handler = logging.StreamHandler(
                console_stream if console_stream is not None else sys.stderr
            )
            console_handler.setLevel(logging.WARNING)
            console_handler.setFormatter(formatter)

            root_logger = logging.getLogger()
            service._previous_root_level = root_logger.level
            root_logger.setLevel(logging.DEBUG)
            root_logger.addHandler(file_handler)
            root_logger.addHandler(console_handler)

            service._file_handler = file_handler
            service._handlers = [file_handler, console_handler]

            cls._instance = service
            return service

    @property
    def _log_path(self):
        """Path of the file currently being written."""
        return self._file_handler.path

    @classmethod
    def get_instance(cls):
        """Return the initialized service."""
        with cls._lock:
            if cls._instance is None:
                raise RuntimeError(
                    "LoggingService has not been initialized"
                )
            return cls._instance

    @classmethod
    def reset(cls):
        """Close the current service and allow a fresh initialization."""
        with cls._lock:
            if cls._instance is not None:
                root_logger = logging.getLogger()

                for handler in cls._instance._handlers:
                    root_logger.removeHandler(handler)
                    handler.flush()
                    handler.close()

                cls._instance._handlers.clear()
                root_logger.setLevel(cls._instance._previous_root_level)

            cls._instance = None

    # Closing and resetting are the same operation: after either, the
    # next initialize() call builds a working service.
    close = reset
