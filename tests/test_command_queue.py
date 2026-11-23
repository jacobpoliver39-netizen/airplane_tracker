import threading

import pytest

from aircraft_tracker import AircraftTracker
from command_queue import ImmediateCommandExecutor, TrackerWorker
from commands import Command, CommandBatch


class RecordingCommand(Command):
    """Records which thread ran it, optionally raising or blocking."""

    def __init__(self, log, name, error=None, gate=None):
        self.log = log
        self.name = name
        self.error = error
        self.gate = gate

    def execute(self, tracker):
        if self.gate is not None:
            self.gate.wait(timeout=5)
        if self.error is not None:
            raise self.error
        self.log.append((self.name, threading.current_thread().name))


def test_immediate_executor_runs_on_calling_thread():
    log = []

    ImmediateCommandExecutor(AircraftTracker()).submit(RecordingCommand(log, "a"))

    assert log == [("a", threading.current_thread().name)]


def test_worker_runs_commands_in_order_on_its_own_thread():
    log = []

    with TrackerWorker(AircraftTracker(), name="test-worker") as worker:
        for name in ("a", "b", "c"):
            worker.submit(RecordingCommand(log, name))
        worker.wait_until_idle()

    assert [name for name, _ in log] == ["a", "b", "c"]
    assert {thread for _, thread in log} == {"test-worker"}
    assert worker.processed_count == 3


def test_worker_survives_a_failing_command():
    log = []

    with TrackerWorker(AircraftTracker()) as worker:
        worker.submit(RecordingCommand(log, "bad", error=RuntimeError("boom")))
        worker.submit(RecordingCommand(log, "good"))
        worker.wait_until_idle()

    assert [name for name, _ in log] == ["good"]
    assert worker.failed_count == 1
    assert worker.processed_count == 1


def test_stop_drains_queued_commands_first():
    log = []
    gate = threading.Event()
    worker = TrackerWorker(AircraftTracker()).start()

    # The first command blocks, so the rest are still queued at stop().
    worker.submit(RecordingCommand(log, "first", gate=gate))
    worker.submit(RecordingCommand(log, "second"))
    worker.submit(RecordingCommand(log, "third"))
    assert worker.queue_depth >= 2

    gate.set()
    worker.stop()

    assert [name for name, _ in log] == ["first", "second", "third"]
    assert not worker.is_running
    assert worker.queue_depth == 0


def test_stop_without_start_is_harmless():
    TrackerWorker(AircraftTracker()).stop()


def test_worker_rejects_non_commands():
    worker = TrackerWorker(AircraftTracker())

    with pytest.raises(TypeError):
        worker.submit(lambda tracker: None)


def test_worker_executes_batches():
    log = []

    with TrackerWorker(AircraftTracker()) as worker:
        worker.submit(CommandBatch(
            [RecordingCommand(log, "a"), RecordingCommand(log, "b")],
            label="test batch",
        ))
        worker.wait_until_idle()

    assert [name for name, _ in log] == ["a", "b"]
    assert worker.processed_count == 1


def test_worker_counts_a_partly_failed_batch_as_failed():
    log = []

    with TrackerWorker(AircraftTracker()) as worker:
        worker.submit(CommandBatch([
            RecordingCommand(log, "bad", error=ValueError("boom")),
            RecordingCommand(log, "good"),
        ]))
        worker.wait_until_idle()

    assert "good" in [name for name, _ in log]
    assert worker.failed_count == 1
    assert worker.processed_count == 0
