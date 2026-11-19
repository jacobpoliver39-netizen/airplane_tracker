import csv

import pytest

import main
import record_opensky
from aircraft_tracker import AircraftTracker
from flight_recording import (
    FlightRecorder,
    convert_csv_to_recording,
    load_recording,
)
from opensky_adapter import OpenSkyAdapter
from opensky_client import OpenSkyRateLimitError
from replay_client import ReplayOpenSkyClient


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


class FakeClock:
    def __init__(self, now=50_000.0):
        self.now = now

    def __call__(self):
        return self.now


# --- recording format ----------------------------------------------------

def test_recording_round_trip(tmp_path):
    path = tmp_path / "session.jsonl"
    write_recording(path, [(1000, [make_state()]), (1015, None)])

    recording = load_recording(path)

    assert recording.header["format"] == 1
    assert "bounding_box" in recording.header
    assert [frame.time for frame in recording.frames] == [1000, 1015]
    assert recording.frames[0].states == [make_state()]
    assert recording.frames[1].states is None
    assert recording.duration_seconds == 15


def test_recorder_appends_to_existing_file_without_second_header(tmp_path):
    path = tmp_path / "session.jsonl"
    write_recording(path, [(1000, [])])
    write_recording(path, [(1015, [])])

    lines = path.read_text().splitlines()

    assert sum('"type":"header"' in line for line in lines) == 1
    assert len(load_recording(path).frames) == 2


def test_load_skips_cut_off_last_line_and_duplicates(tmp_path):
    path = tmp_path / "session.jsonl"
    write_recording(path, [(1015, []), (1000, []), (1000, [])])

    with path.open("a") as recording_file:
        recording_file.write('{"type":"frame","time":1030,"sta')

    frames = load_recording(path).frames

    assert [frame.time for frame in frames] == [1000, 1015]


def test_convert_csv_groups_rows_into_frames(tmp_path):
    csv_path = tmp_path / "observations.csv"
    rows = [
        ("2026-11-12T15:06:03+00:00", "1000", "AAA1", "998", "23.1", "False"),
        ("2026-11-12T15:06:03+00:00", "1000", "BBB2", "1000", "23.2", "False"),
        ("2026-11-12T15:06:18+00:00", "1015", "AAA1", "1014", "23.3", "True"),
    ]

    with csv_path.open("w", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow([
            "collected_at", "response_time", "icao24", "callsign",
            "origin_country", "time_position", "last_contact", "longitude",
            "latitude", "baro_altitude_m", "on_ground", "velocity_mps",
            "true_track_deg", "vertical_rate_mps", "geo_altitude_m",
            "squawk", "spi", "position_source", "category",
        ])
        for collected_at, response_time, callsign, time_position, lon, ground in rows:
            writer.writerow([
                collected_at, response_time, "abc", callsign, "Greece",
                time_position, time_position, lon, "40.7", "3000.5", ground,
                "200.0", "90.0", "", "3100", "1234", "False", "0", "",
            ])

    output = tmp_path / "converted.jsonl"
    assert convert_csv_to_recording(csv_path, output) == 2

    frames = load_recording(output).frames
    first_state = frames[0].states[0]

    assert [frame.time for frame in frames] == [1000, 1015]
    assert len(frames[0].states) == 2
    assert first_state[3] == 998 and first_state[5] == 23.1
    assert first_state[8] is False and frames[1].states[0][8] is True
    assert first_state[11] is None and first_state[14] == "1234"
    # The tracker can parse the rebuilt state arrays.
    assert OpenSkyAdapter.parse_state(first_state).callsign == "AAA1"


# --- replay client -------------------------------------------------------

@pytest.fixture
def recording(tmp_path):
    path = tmp_path / "session.jsonl"
    write_recording(path, [
        (1000, [make_state(time_position=999)]),
        (1015, [make_state(time_position=1014, longitude=23.2)]),
        (1045, [make_state(time_position=1044, longitude=23.4)]),
    ])
    return path


def test_replay_shifts_timestamps_to_the_present(recording):
    clock = FakeClock(50_000)
    client = ReplayOpenSkyClient(recording, clock=clock)

    response_time, states = client.get_states()

    assert response_time == 50_000
    assert states[0][3] == 49_999 and states[0][4] == 49_999
    assert states[0][5] == 23.1


def test_replay_waits_for_recorded_gaps(recording):
    clock = FakeClock(50_000)
    client = ReplayOpenSkyClient(recording, clock=clock)

    client.get_states()
    assert client.seconds_until_next_poll() == 15

    clock.now += 4  # the poll itself took some time
    assert client.seconds_until_next_poll() == 11

    clock.now = 50_015
    assert client.get_states()[0] == 50_015
    assert client.seconds_until_next_poll() == 30


def test_replay_speed_shortens_waits(recording):
    clock = FakeClock(50_000)
    client = ReplayOpenSkyClient(recording, speed=3, clock=clock)

    client.get_states()

    assert client.seconds_until_next_poll() == 5


def test_replay_start_offset_skips_frames(recording):
    client = ReplayOpenSkyClient(
        recording, start_offset_seconds=10, clock=FakeClock(50_000)
    )

    _, states = client.get_states()

    assert states[0][5] == 23.2


def test_replay_returns_no_aircraft_after_the_end(recording):
    clock = FakeClock(50_000)
    client = ReplayOpenSkyClient(recording, clock=clock)

    for _ in range(3):
        client.get_states()
    clock.now = 50_100

    assert client.get_states() == (50_100, [])


def test_replay_loop_keeps_timestamps_increasing(recording):
    clock = FakeClock(50_000)
    client = ReplayOpenSkyClient(recording, loop=True, clock=clock)
    times = [client.get_states()[0] for _ in range(4)]

    # Lap length = 45 s of traffic + the median gap (22.5 s).
    assert times == [50_000, 50_015, 50_045, 50_067.5]


def test_replay_rejects_empty_recording(tmp_path):
    path = tmp_path / "empty.jsonl"
    write_recording(path, [])

    with pytest.raises(ValueError):
        ReplayOpenSkyClient(path)


def test_replay_drives_the_tracker(recording):
    clock = FakeClock(50_000)
    client = ReplayOpenSkyClient(recording, clock=clock)
    tracker = AircraftTracker()

    for wall_time in (50_000, 50_015, 50_045):
        clock.now = wall_time
        main.poll_once(client, tracker)

    plane = tracker.aircrafts["TEST123"]
    assert plane.timestamp == 50_044
    assert plane.longitude == 23.4
    assert len(plane.location_history) == 3


# --- recorder loop -------------------------------------------------------

class FakeLiveClient:
    authenticated = False

    def __init__(self, results):
        self._results = list(results)

    def get_states(self):
        result = self._results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def test_record_writes_frames_and_survives_rate_limit(tmp_path, monkeypatch):
    path = tmp_path / "session.jsonl"
    client = FakeLiveClient([
        (1000, [make_state()]),
        OpenSkyRateLimitError(60),
        (1075, None),
    ])
    sleeps = []

    def fake_sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) == 3:
            raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        record_opensky.record(path, client=client, sleep=fake_sleep)

    assert [frame.time for frame in load_recording(path).frames] == [1000, 1075]
    assert sleeps[1] >= 59


def test_replay_shortens_long_gaps(tmp_path):
    path = tmp_path / "gappy.jsonl"
    write_recording(path, [
        (1000, [make_state(time_position=999)]),
        (9000, [make_state(time_position=8999)]),
    ])
    clock = FakeClock(50_000)
    client = ReplayOpenSkyClient(path, clock=clock, max_gap_seconds=300)

    client.get_states()
    assert client.seconds_until_next_poll() == 300

    clock.now = 50_300
    response_time, states = client.get_states()
    assert response_time == 50_300
    assert states[0][3] == 50_299


def test_replay_next_poll_is_immediate_before_first_frame(recording):
    client = ReplayOpenSkyClient(recording, clock=FakeClock())

    assert client.seconds_until_next_poll() == 0


class RecordingStopEvent:
    """Records waits and moves the fake clock forward by each one."""

    def __init__(self, stop_after, clock):
        self.waits = []
        self._stop_after = stop_after
        self._clock = clock

    def is_set(self):
        return len(self.waits) >= self._stop_after

    def wait(self, timeout=None):
        self.waits.append(timeout)
        self._clock.now += timeout


def test_polling_loop_waits_for_replay_gaps(recording):
    clock = FakeClock(50_000)
    client = ReplayOpenSkyClient(recording, clock=clock)
    stop_event = RecordingStopEvent(stop_after=2, clock=clock)

    main._poll_until_stopped(client, AircraftTracker(), stop_event)

    # Waits are timed from the frame just served: 15 s, then 30 s.
    assert stop_event.waits == [15, 30]
