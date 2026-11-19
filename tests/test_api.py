import inspect
import threading
import typing

import pytest

import api
from fastapi.testclient import TestClient

from aircraft import Aircraft
from aircraft_tracker import AircraftTracker
from ranking_strategies import RANKING_STRATEGIES, FastestApproachStrategy


class FakeAircraft:
    def __init__(self, callsign, distance, approach_speed):
        self.callsign = callsign
        self.latitude = 42.0
        self.longitude = -73.0
        self.altitude = 12000
        self.velocity = 250
        self.heading = 90
        self.distance_from_user = distance
        self.approach_speed = approach_speed
        self.timestamp = 1000

    def get_distance_from_user(self):
        return self.distance_from_user

    def get_approach_speed_towards_user(self):
        return self.approach_speed

    def get_nearest_distance_from_user(self):
        return self.distance_from_user

    def get_nearest_distance_time(self):
        return 60.0

    def get_curved_nearest_approach(self):
        return None

    def get_curved_trajectory(self, sample_interval_seconds=5):
        return None

    def get_straight_trajectory(self, sample_interval_seconds=5):
        return [[self.latitude, self.longitude], [self.latitude, self.longitude + 0.1]]


def make_tracker():
    tracker = AircraftTracker()
    tracker.add_aircraft(FakeAircraft("NEAR_SLOW", 5.0, 100.0))
    tracker.add_aircraft(FakeAircraft("FAR_FAST", 30.0, 400.0))
    return tracker


def test_aircraft_endpoint_returns_nearest_first_by_default(monkeypatch):
    tracker = make_tracker()
    monkeypatch.setattr(api, "aircraft_tracker", tracker)

    # Not using the context manager means the polling lifespan doesn't start.
    client = TestClient(api.app)
    response = client.get("/aircraft")

    assert response.status_code == 200
    assert [plane["callsign"] for plane in response.json()] == [
        "NEAR_SLOW",
        "FAR_FAST",
    ]


def test_aircraft_endpoint_uses_selected_ranking_strategy(monkeypatch):
    tracker = make_tracker()
    tracker.set_ranking_strategy(FastestApproachStrategy())
    monkeypatch.setattr(api, "aircraft_tracker", tracker)

    client = TestClient(api.app)
    response = client.get("/aircraft")

    assert response.status_code == 200
    assert [plane["callsign"] for plane in response.json()] == [
        "FAR_FAST",
        "NEAR_SLOW",
    ]


@pytest.mark.parametrize(
    "rank, expected",
    [
        ("nearest", ["NEAR_SLOW", "FAR_FAST"]),
        ("fastest", ["FAR_FAST", "NEAR_SLOW"]),
        # FakeAircraft has no curved prediction, so this uses the
        # straight-line nearest distance (5 vs 30 miles).
        ("predicted", ["NEAR_SLOW", "FAR_FAST"]),
    ],
)
def test_aircraft_endpoint_ranks_by_query_parameter(monkeypatch, rank, expected):
    tracker = make_tracker()
    monkeypatch.setattr(api, "aircraft_tracker", tracker)

    client = TestClient(api.app)
    response = client.get("/aircraft", params={"rank": rank})

    assert response.status_code == 200
    assert [plane["callsign"] for plane in response.json()] == expected


def test_rank_parameter_does_not_change_tracker_default(monkeypatch):
    tracker = make_tracker()
    monkeypatch.setattr(api, "aircraft_tracker", tracker)
    client = TestClient(api.app)

    client.get("/aircraft", params={"rank": "fastest"})
    response = client.get("/aircraft")

    assert [plane["callsign"] for plane in response.json()] == [
        "NEAR_SLOW",
        "FAR_FAST",
    ]


def test_aircraft_endpoint_rejects_unknown_rank(monkeypatch):
    monkeypatch.setattr(api, "aircraft_tracker", make_tracker())

    client = TestClient(api.app)
    response = client.get("/aircraft", params={"rank": "slowest"})

    assert response.status_code == 422


def test_rank_options_match_ranking_strategies():
    # The Literal on the endpoint must list exactly the registered strategies.
    rank_param = inspect.signature(api.get_aircraft).parameters["rank"]
    literal = typing.get_args(rank_param.annotation)[0]

    assert set(typing.get_args(literal)) == set(RANKING_STRATEGIES)


def test_aircraft_endpoint_preserves_response_fields(monkeypatch):
    monkeypatch.setattr(api, "aircraft_tracker", make_tracker())

    client = TestClient(api.app)
    response = client.get("/aircraft")

    assert response.status_code == 200
    plane = response.json()[0]
    assert set(plane) == {
        "id",
        "callsign",
        "latitude",
        "longitude",
        "altitude",
        "speed",
        "heading",
        "distance",
        "nearest_distance",
        "nearest_distance_time",
        "curved_nearest_distance",
        "curved_nearest_distance_time",
        "timestamp",
        "trajectory_step_seconds",
        "straight_trajectory",
        "curved_trajectory",
    }
    assert plane["curved_nearest_distance"] is None
    assert plane["curved_nearest_distance_time"] is None
    assert plane["curved_trajectory"] is None


def make_real_aircraft(callsign, timestamp, longitude):
    return Aircraft(
        callsign, timestamp, longitude, 40.6, 10000, 90.0,
        "Test", 300.0, 23.0, 40.6,
    )


def test_aircraft_endpoint_is_safe_while_tracker_is_updated(monkeypatch):
    tracker = AircraftTracker()
    tracker.add_aircraft(make_real_aircraft("STEADY", 1000, 22.5))
    monkeypatch.setattr(api, "aircraft_tracker", tracker)

    stop = threading.Event()
    errors = []

    def keep_updating():
        # Mimic the polling thread: grow histories and churn aircraft.
        step = 0
        try:
            while not stop.is_set():
                step += 1
                with tracker.lock:
                    tracker.aircrafts["STEADY"].update_info(
                        22.5 + step * 0.001, 40.6, 1000 + step,
                        10000, 90.0, 300.0,
                    )
                    tracker.add_aircraft(
                        make_real_aircraft(f"TMP{step}", 1000, 22.6)
                    )
                    if step > 1:
                        tracker.remove_aircraft(f"TMP{step - 1}")
        except Exception as error:  # pragma: no cover - reported below
            errors.append(error)

    writer = threading.Thread(target=keep_updating)
    writer.start()

    try:
        client = TestClient(api.app)
        for _ in range(50):
            response = client.get("/aircraft")
            assert response.status_code == 200
    finally:
        stop.set()
        writer.join(timeout=5)

    assert errors == []


# --- data source endpoints ----------------------------------------------

from polling_service import RecordingNotFoundError, SourceBusyError


class FakePollingService:
    def __init__(self, error=None):
        self.calls = []
        self.error = error

    def _record(self, *call):
        self.calls.append(call)
        if self.error is not None:
            raise self.error
        return {"mode": "replay" if call[0] != "live" else "live"}

    def status(self):
        return {"mode": "live", "clock": {"now": 1.0, "speed": 1.0}}

    def list_recordings(self):
        return [{"name": "session.jsonl", "kind": "recording"}]

    def start_replay(self, name, speed=1.0, loop=False):
        return self._record("replay", name, speed, loop)

    def set_speed(self, speed):
        return self._record("speed", speed)

    def go_live(self):
        return self._record("live")


@pytest.fixture
def fake_service(monkeypatch):
    service = FakePollingService()
    monkeypatch.setattr(api, "polling_service", service)
    return service


def test_source_and_recordings_endpoints(fake_service):
    client = TestClient(api.app)

    assert client.get("/source").json()["mode"] == "live"
    assert client.get("/recordings").json()[0]["name"] == "session.jsonl"


def test_start_replay_endpoint(fake_service):
    client = TestClient(api.app)

    response = client.post(
        "/source/replay", json={"recording": "session.jsonl", "speed": 10}
    )

    assert response.status_code == 200
    assert fake_service.calls == [("replay", "session.jsonl", 10.0, False)]


def test_start_replay_defaults_to_normal_speed(fake_service):
    TestClient(api.app).post("/source/replay", json={"recording": "a.jsonl"})

    assert fake_service.calls == [("replay", "a.jsonl", 1.0, False)]


def test_speed_and_live_endpoints(fake_service):
    client = TestClient(api.app)

    assert client.post("/source/replay/speed", json={"speed": 30}).status_code == 200
    assert client.post("/source/live").status_code == 200
    assert fake_service.calls == [("speed", 30.0), ("live",)]


@pytest.mark.parametrize("speed", [0, -5, 10_000])
def test_speed_outside_limits_is_rejected(fake_service, speed):
    response = TestClient(api.app).post(
        "/source/replay/speed", json={"speed": speed}
    )

    assert response.status_code == 422
    assert fake_service.calls == []


@pytest.mark.parametrize(
    "error, status",
    [
        (RecordingNotFoundError("nope"), 404),
        (SourceBusyError("busy"), 503),
        (ValueError("bad"), 400),
    ],
)
def test_source_errors_map_to_status_codes(monkeypatch, error, status):
    monkeypatch.setattr(api, "polling_service", FakePollingService(error))

    response = TestClient(api.app).post(
        "/source/replay", json={"recording": "x.jsonl"}
    )

    assert response.status_code == status
