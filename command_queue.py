"""
Where commands are executed.

Producers (the polling loop) call `submit(command)` and don't care how
the command reaches the tracker:

- ImmediateCommandExecutor runs it straight away on the caller's thread
  (tests, scripts).
- TrackerWorker puts it on a queue and a single consumer thread runs it.
  That thread is the only code that changes the tracker.
"""

import logging
import queue
import threading
from abc import ABC, abstractmethod

from commands import Command, CommandBatch

logger = logging.getLogger(__name__)

# Put on the queue by stop(); everything submitted before it still runs.
_STOP = object()


class CommandExecutor(ABC):

    @abstractmethod
    def submit(self, command: Command) -> None:
        pass


class ImmediateCommandExecutor(CommandExecutor):
    """Execute each command on the calling thread as soon as it is submitted."""

    def __init__(self, tracker):
        self.tracker = tracker

    def submit(self, command):
        command.execute(self.tracker)


class TrackerWorker(CommandExecutor):
    """
    Consumer side of the producer/consumer pair: a background thread that
    takes commands off a FIFO queue and executes them against the tracker.

    A command that raises is logged and skipped, so one bad command
    cannot stop the worker.
    """

    def __init__(self, tracker, name="tracker-worker"):
        self.tracker = tracker
        self._queue = queue.Queue()
        self._thread = threading.Thread(target=self._run, name=name, daemon=True)
        self._stats_lock = threading.Lock()
        self._processed = 0
        self._failed = 0

    # --- producer side ---------------------------------------------------

    def submit(self, command):
        if not isinstance(command, Command):
            raise TypeError("Only Command objects can be submitted")

        self._queue.put(command)

    # --- lifecycle -------------------------------------------------------

    def start(self):
        self._thread.start()
        return self

    def stop(self, timeout=10):
        """Finish the commands already queued, then end the thread."""
        if not self._thread.is_alive():
            return

        self._queue.put(_STOP)
        self._thread.join(timeout)

        if self._thread.is_alive():
            logger.warning(
                "Tracker worker did not stop within %s s (%d commands left)",
                timeout,
                self.queue_depth,
            )

    def wait_until_idle(self):
        """Block until every command submitted so far has been executed."""
        self._queue.join()

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc_info):
        self.stop()

    # --- monitoring ------------------------------------------------------

    @property
    def queue_depth(self):
        return self._queue.qsize()

    @property
    def processed_count(self):
        with self._stats_lock:
            return self._processed

    @property
    def failed_count(self):
        with self._stats_lock:
            return self._failed

    @property
    def is_running(self):
        return self._thread.is_alive()

    # --- consumer loop ---------------------------------------------------

    def _run(self):
        while True:
            command = self._queue.get()

            try:
                if command is _STOP:
                    return

                self._execute(command)
            finally:
                self._queue.task_done()

    def _execute(self, command):
        try:
            command.execute(self.tracker)
        except Exception:
            with self._stats_lock:
                self._failed += 1
            logger.exception("Command failed: %s", type(command).__name__)
            return

        with self._stats_lock:
            self._processed += 1

        if isinstance(command, CommandBatch):
            logger.info(
                "Applied %s (%d commands): %d aircraft tracked",
                command.label,
                len(command),
                len(self.tracker.aircrafts),
            )
