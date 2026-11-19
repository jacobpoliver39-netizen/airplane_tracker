import os
import time

import pytest

import config
import polling_service
from aircraft_tracker import AircraftTracker
from flight_recording import FlightRecorder
from logging_service import LoggingService
from polling_service import (
    PollingService,
    RecordingNotFoundError,
)


@pytest.fixture(autouse=True)
def isolated_logging(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "REPLAY_FILE", None)
    LoggingService.reset()
    LoggingService.initialize(log_dir=tmp_path / "logs")
    yield
    LoggingService.reset()


def make_state(callsign="TEST123 ", time_position=1000, longitude=23.1):
    return [
        "abc123", callsign, "Greece", time_position, time_position,
        longitude, 40.7, 3000.0, False, 200.0, 90.0,
        0.0, None, 3000.0, "1234", False, 0,
    ]


def write_recording(path, frames):
    with FlightRecorder(path) as recorder:
        for response_time, states in frames:
            recorder.record(response_time, states)


class FakeLiveClient:
    """Reports one live aircraft per poll and then waits a long time."""

    authenticated = False

    def __init__(self, callsign="LIVE1"):
        self.callsign = callsign
        self.closed = False

    def get_states(self):
        now = time.time()
        return now, [make_state(callsign=self.callsign, time_position=now)]

    def seconds_until_next_poll(self):
        return 60

    def close(self):
        self.closed = True


def wait_for(condition, timeout=5):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if condition():
            return True
        time.sleep(0.02)
    return False


@pytest.fixture
def dirs(tmp_path):
    data_dir = tmp_path / "data"
    recordings_dir = data_dir / "recordings"
    recordings_dir.mkdir(parents=True)
    write_recording(recordings_dir / "session.jsonl", [
        (1000, [make_state(callsign="REPLAY1 ", time_position=999)]),
        (1015, [make_state(callsign="REPLAY1 ", time_position=1014, longitude=23.2)]),
    ])
    return data_dir, recordings_dir


@pytest.fixture
def service(dirs):
    data_dir, recordings_dir = dirs
    live_clients = []

    def live_factory():
        client = FakeLiveClient()
        live_clients.append(client)
        return client

    service = PollingService(
        AircraftTracker(),
        live_client_factory=live_factory,
        recordings_dir=recordings_dir,
        data_dir=data_dir,
    )
    service.live_clients = live_clients
    service.start()
    yield service
    service.stop()


def tracked(service):
    return set(service._tracker.aircrafts)


# --- listing -------------------------------------------------------------

def test_lists_recordings_and_csvs_but_not_converted_copies(dirs):
    data_dir, recordings_dir = dirs
    (data_dir / "opensky_observations.csv").write_text("x")
    (recordings_dir / polling_service.CSV_CACHE_DIRNAME).mkdir()
    (recordings_dir / polling_service.CSV_CACHE_DIRNAME / "copy.jsonl").write_text("")

    service = PollingService(
        AircraftTracker(), recordings_dir=recordings_dir, data_dir=data_dir
    )

    assert [(r["name"], r["kind"]) for r in service.list_recordings()] == [
        ("session.jsonl", "recording"),
        ("opensky_observations.csv", "csv"),
    ]


# --- switching -----------------------------------------------------------

def test_starts_live(service):
    assert service.status()["mode"] == "live"
    assert wait_for(lambda: tracked(service) == {"LIVE1"})


def test_start_replay_clears_live_aircraft_and_replays(service):
    assert wait_for(lambda: tracked(service) == {"LIVE1"})

    status = service.start_replay("session.jsonl", speed=2)

    assert status["mode"] == "replay"
    assert status["recording"] == "session.jsonl"
    assert status["speed"] == 2
    assert status["progress"]["frame_count"] == 2
    assert wait_for(lambda: tracked(service) == {"REPLAY1"})
    assert service.live_clients[0].closed


def test_unknown_recording_keeps_current_source(service):
    with pytest.raises(RecordingNotFoundError):
        service.start_replay("../secrets.jsonl")

    assert service.status()["mode"] == "live"
    assert wait_for(lambda: tracked(service) == {"LIVE1"})


def test_unreadable_recording_keeps_current_source(service, dirs):
    _, recordings_dir = dirs
    write_recording(recordings_dir / "empty.jsonl", [])

    with pytest.raises(ValueError):
        service.start_replay("empty.jsonl")

    assert service.status()["mode"] == "live"
    assert service._thread.is_alive()


def test_set_speed_keeps_aircraft_and_recording(service):
    service.start_replay("session.jsonl")
    assert wait_for(lambda: tracked(service) == {"REPLAY1"})
    history = len(service._tracker.aircrafts["REPLAY1"].location_history)

    status = service.set_speed(10)

    assert status["speed"] == 10
    assert status["recording"] == "session.jsonl"
    assert tracked(service) == {"REPLAY1"}
    # Resumes from the same place: at 10x, the 15 s gap takes 1.5 s.
    assert wait_for(
        lambda: len(service._tracker.aircrafts["REPLAY1"].location_history)
        == history + 1,
        timeout=4,
    )
    assert status["clock"]["speed"] == 10


def test_set_speed_while_live_is_rejected(service):
    with pytest.raises(ValueError):
        service.set_speed(5)


@pytest.mark.parametrize("speed", [0, -1, 1000])
def test_out_of_range_speed_is_rejected(service, speed):
    with pytest.raises(ValueError):
        service.start_replay("session.jsonl", speed=speed)


def test_go_live_clears_replay(service):
    service.start_replay("session.jsonl")
    assert wait_for(lambda: tracked(service) == {"REPLAY1"})

    status = service.go_live()

    assert status["mode"] == "live"
    assert wait_for(lambda: tracked(service) == {"LIVE1"})


def test_live_clock_is_wall_clock(service):
    clock = service.status()["clock"]

    assert clock["speed"] == 1
    assert abs(clock["now"] - time.time()) < 1


# --- CSV conversion ------------------------------------------------------

def test_csv_is_converted_once_and_again_when_it_changes(dirs, monkeypatch):
    data_dir, recordings_dir = dirs
    csv_path = data_dir / "observations.csv"
    csv_path.write_text("x")
    conversions = []

    def fake_convert(source, output):
        conversions.append(source)
        write_recording(output, [(1000, [make_state()])])
        return 1

    monkeypatch.setattr(polling_service, "convert_csv_to_recording", fake_convert)
    service = PollingService(
        AircraftTracker(),
        live_client_factory=FakeLiveClient,
        recordings_dir=recordings_dir,
        data_dir=data_dir,
    )

    try:
        service.start_replay("observations.csv")
        service.start_replay("observations.csv")
        assert len(conversions) == 1

        later = time.time() + 10
        os.utime(csv_path, (later, later))
        service.start_replay("observations.csv")
        assert len(conversions) == 2

        converted = recordings_dir / polling_service.CSV_CACHE_DIRNAME
        assert [p.name for p in converted.iterdir()] == ["observations.jsonl"]
    finally:
        service.stop()
