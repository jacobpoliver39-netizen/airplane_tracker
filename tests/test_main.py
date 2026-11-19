import threading

import pytest
import requests

import config
import main
from aircraft_tracker import AircraftTracker
from logging_service import LoggingService
from opensky_client import OpenSkyRateLimitError


@pytest.fixture(autouse=True)
def isolated_logging(tmp_path):
    LoggingService.reset()
    LoggingService.initialize(log_dir=tmp_path)
    yield
    LoggingService.reset()


def make_state(
    callsign="TEST123 ",
    time_position=1000,
    longitude=23.1,
    latitude=40.7,
    baro_altitude=3000.0,
    on_ground=False,
    velocity=200.0,
    heading=90.0,
):
    """Build an OpenSky state array (17 fields, as the API returns)."""
    return [
        "abc123", callsign, "Greece", time_position, time_position,
        longitude, latitude, baro_altitude, on_ground, velocity, heading,
        0.0, None, baro_altitude, "1234", False, 0,
    ]


# --- apply_states --------------------------------------------------------

def test_apply_states_adds_and_updates_aircraft():
    tracker = AircraftTracker()

    main.apply_states(tracker, [make_state(time_position=1000)], 1000)
    main.apply_states(
        tracker, [make_state(time_position=1015, longitude=23.2)], 1015
    )

    aircraft = tracker.aircrafts["TEST123"]
    assert aircraft.longitude == 23.2
    assert len(aircraft.location_history) == 2


def test_apply_states_skips_bad_states_without_failing():
    tracker = AircraftTracker()
    states = [
        make_state(callsign="GOOD1"),
        make_state(callsign="NOPOS", longitude=None),
        "garbage",
        make_state(callsign="NOSPEED", velocity=None),
    ]

    observed = main.apply_states(tracker, states, 1000)

    assert observed == 1
    assert set(tracker.aircrafts) == {"GOOD1"}


def test_apply_states_never_adds_low_or_grounded_aircraft():
    tracker = AircraftTracker()
    states = [
        make_state(callsign="GROUND", on_ground=True, baro_altitude=None),
        make_state(callsign="LOW", baro_altitude=1.0),  # about 3 ft
        make_state(callsign="HIGH"),
    ]

    main.apply_states(tracker, states, 1000)

    assert set(tracker.aircrafts) == {"HIGH"}


def test_apply_states_removes_tracked_aircraft_once_it_lands():
    tracker = AircraftTracker()
    main.apply_states(tracker, [make_state(time_position=1000)], 1000)

    main.apply_states(
        tracker,
        [make_state(time_position=1015, on_ground=True, baro_altitude=None)],
        1015,
    )

    assert tracker.aircrafts == {}


def test_apply_states_keeps_missing_aircraft_for_grace_period():
    tracker = AircraftTracker()
    main.apply_states(tracker, [make_state(time_position=1000)], 1000)

    # One missed poll, still inside the grace period.
    main.apply_states(tracker, [], 1000 + config.POLL_INTERVAL_SECONDS)
    assert "TEST123" in tracker.aircrafts

    # Past the grace period.
    main.apply_states(
        tracker, None, 1000 + config.MISSING_AIRCRAFT_GRACE_SECONDS + 1
    )
    assert tracker.aircrafts == {}


# --- build_poll_commands / poll_once --------------------------------------

def test_build_poll_commands_creates_updates_then_removals():
    from commands import (
        RemoveLowAltitudeAircraftCommand,
        RemoveMissingAircraftCommand,
        UpdateAircraftCommand,
    )

    batch, observed = main.build_poll_commands(
        [make_state(callsign="A"), make_state(callsign="B"), "garbage"], 1000
    )

    assert observed == 2
    assert [type(command) for command in batch.commands] == [
        UpdateAircraftCommand,
        UpdateAircraftCommand,
        RemoveMissingAircraftCommand,
        RemoveLowAltitudeAircraftCommand,
    ]
    assert batch.commands[2].observed_callsigns == {"A", "B"}


class CollectingExecutor:
    def __init__(self):
        self.submitted = []

    def submit(self, command):
        self.submitted.append(command)


def test_poll_once_submits_one_batch_without_touching_a_tracker():
    executor = CollectingExecutor()
    stop_event = threading.Event()
    client = FakeClient([(1000, [make_state()])], stop_event)

    main.poll_once(client, executor)

    assert len(executor.submitted) == 1
    assert len(executor.submitted[0]) == 3  # update + 2 removals


class ThreadRecordingTracker(AircraftTracker):
    def __init__(self):
        super().__init__()
        self.mutating_threads = set()

    def add_aircraft(self, aircraft):
        self.mutating_threads.add(threading.current_thread().name)
        super().add_aircraft(aircraft)


def test_main_applies_updates_on_the_worker_thread():
    tracker = ThreadRecordingTracker()
    stop_event = RecordingEvent()
    client = FakeClient([(1000, [make_state()])], stop_event)

    main.main(stop_event, client=client, tracker=tracker)

    assert set(tracker.aircrafts) == {"TEST123"}
    assert tracker.mutating_threads == {"tracker-worker"}


# --- polling loop --------------------------------------------------------

class FakeClient:
    """Returns or raises the queued results, then stops the loop."""

    authenticated = False

    def __init__(self, results, stop_event):
        self._results = list(results)
        self._stop_event = stop_event
        self.calls = 0

    def seconds_until_next_poll(self):
        return config.POLL_INTERVAL_SECONDS

    def get_states(self):
        self.calls += 1

        if len(self._results) <= 1:
            self._stop_event.set()

        result = self._results.pop(0)

        if isinstance(result, Exception):
            raise result

        return result


class RecordingEvent(threading.Event):
    """Records requested waits without actually waiting."""

    def __init__(self):
        super().__init__()
        self.waits = []

    def wait(self, timeout=None):
        self.waits.append(timeout)
        return self.is_set()


def test_failed_request_leaves_tracker_unchanged():
    tracker = AircraftTracker()
    main.apply_states(tracker, [make_state()], 1000)

    stop_event = RecordingEvent()
    client = FakeClient([requests.ConnectionError("down")], stop_event)

    main.main(stop_event, client=client, tracker=tracker)

    assert set(tracker.aircrafts) == {"TEST123"}


def test_polling_loop_survives_unexpected_errors():
    tracker = AircraftTracker()
    stop_event = RecordingEvent()
    client = FakeClient(
        [
            RuntimeError("unexpected bug"),
            (1000, [make_state()]),
        ],
        stop_event,
    )

    main.main(stop_event, client=client, tracker=tracker)

    assert client.calls == 2
    assert set(tracker.aircrafts) == {"TEST123"}


def test_polling_loop_waits_for_rate_limit_retry_after():
    stop_event = RecordingEvent()
    client = FakeClient([OpenSkyRateLimitError(3600)], stop_event)

    main.main(stop_event, client=client, tracker=AircraftTracker())

    assert stop_event.waits == [3600]


def test_wait_first_waits_before_the_first_poll():
    stop_event = RecordingEvent()
    client = FakeClient([(1000, [make_state()])], stop_event)

    main.main(stop_event, client=client, tracker=AircraftTracker(), wait_first=True)

    # One wait before the poll, one after it.
    assert stop_event.waits == [config.POLL_INTERVAL_SECONDS] * 2
    assert client.calls == 1
