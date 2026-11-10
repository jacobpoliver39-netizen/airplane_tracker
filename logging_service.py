import logging
import sys
import threading
from datetime import date
from pathlib import Path
from typing import TextIO


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
        """Create the shared logging service, or return the existing one."""
        with cls._lock:
            if cls._instance is not None:
                return cls._instance

            service = object.__new__(cls)
            service._handlers = []

            directory = Path(log_dir)
            directory.mkdir(parents=True, exist_ok=True)

            if log_date is None:
                log_date = date.today()

            filename = f"jacobsky_{log_date:%Y-%m-%d}.log"
            log_path = directory / filename

            formatter = logging.Formatter(
                "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
            )

            file_handler = logging.FileHandler(
                log_path,
                encoding="utf-8",
            )
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

            service._handlers = [file_handler, console_handler]
            service._log_path = log_path

            cls._instance = service
            return service

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
    def close(cls):
        """Detach and close this service's handlers."""
        with cls._lock:
            if cls._instance is None:
                return

            root_logger = logging.getLogger()

            for handler in cls._instance._handlers:
                root_logger.removeHandler(handler)
                handler.flush()
                handler.close()

            cls._instance._handlers.clear()
            root_logger.setLevel(cls._instance._previous_root_level)

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
