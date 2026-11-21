import inspect
import threading
import typing

import pytest
from fastapi.testclient import TestClient

import api
import config
from aircraft import Aircraft
from aircraft_state import AircraftLifecycle
from aircraft_tracker import AircraftTracker
from ranking_strategies import RANKING_STRATEGIES, FastestApproachStrategy
from tracker_observers import attach_default_observers


class FakeAircraft:
    """
    Just the state the endpoint and the real TrajectoryPredictor read.
    With no location history there is no curved prediction.
    """

    def __init__(self, callsign, distance, approach_speed):
        self.callsign = callsign
        self.lifecycle = AircraftLifecycle(callsign)
        self.latitude = 42.0
        self.longitude = -73.0
        self.altitude = 12000
        self.velocity = 250
        self.heading = 90
        self.distance_from_user = distance
        self.approach_speed = approach_speed
        self.timestamp = 1000
        self.user_longitude = 23.0
        self.user_latitude = 40.6
        self.location_history = {}

    def get_distance_from_user(self):
        return self.distance_from_user

    def get_approach_speed_towards_user(self):
        return self.approach_speed


def make_app(tracker=None, polling=None, observers=None):
    """An app with the given services; polling is never started."""
    tracker = tracker if tracker is not None else AircraftTracker()
    return api.create_app(api.AppServices(
        tracker=tracker,
        polling=polling if polling is not None else FakePollingService(),
        observers=(
            observers if observers is not None
            else attach_default_observers(tracker, geofences=[])
        ),
    ))


def make_tracker():
    tracker = AircraftTracker()
    tracker.add_aircraft(FakeAircraft("NEAR_SLOW", 5.0, 100.0))
    tracker.add_aircraft(FakeAircraft("FAR_FAST", 30.0, 400.0))
    return tracker


def test_aircraft_endpoint_returns_nearest_first_by_default(monkeypatch):
    tracker = make_tracker()
    app = make_app(tracker=tracker)

    # Not using the context manager means the polling lifespan doesn't start.
    client = TestClient(app)
    response = client.get("/aircraft")

    assert response.status_code == 200
    assert [plane["callsign"] for plane in response.json()] == [
        "NEAR_SLOW",
        "FAR_FAST",
    ]


def test_aircraft_endpoint_uses_selected_ranking_strategy(monkeypatch):
    tracker = make_tracker()
    tracker.set_ranking_strategy(FastestApproachStrategy())
    app = make_app(tracker=tracker)

    client = TestClient(app)
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
        # Both fakes share a position, so their predicted approach ties
        # and the current distance (5 vs 30 miles) decides.
        ("predicted", ["NEAR_SLOW", "FAR_FAST"]),
    ],
)
def test_aircraft_endpoint_ranks_by_query_parameter(monkeypatch, rank, expected):
    tracker = make_tracker()
    app = make_app(tracker=tracker)

    client = TestClient(app)
    response = client.get("/aircraft", params={"rank": rank})

    assert response.status_code == 200
    assert [plane["callsign"] for plane in response.json()] == expected


def test_rank_parameter_does_not_change_tracker_default(monkeypatch):
    tracker = make_tracker()
    app = make_app(tracker=tracker)
    client = TestClient(app)

    client.get("/aircraft", params={"rank": "fastest"})
    response = client.get("/aircraft")

    assert [plane["callsign"] for plane in response.json()] == [
        "NEAR_SLOW",
        "FAR_FAST",
    ]


def test_aircraft_endpoint_rejects_unknown_rank(monkeypatch):
    app = make_app(tracker=make_tracker())

    client = TestClient(app)
    response = client.get("/aircraft", params={"rank": "slowest"})

    assert response.status_code == 422


def test_rank_options_match_ranking_strategies():
    # The Literal on the endpoint must list exactly the registered strategies.
    rank_param = inspect.signature(api.get_aircraft).parameters["rank"]
    literal = typing.get_args(rank_param.annotation)[0]

    assert set(typing.get_args(literal)) == set(RANKING_STRATEGIES)


def test_aircraft_endpoint_preserves_response_fields(monkeypatch):
    app = make_app(tracker=make_tracker())

    client = TestClient(app)
    response = client.get("/aircraft")

    assert response.status_code == 200
    plane = response.json()[0]
    assert set(plane) == {
        "id",
        "callsign",
        "state",
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
    app = make_app(tracker=tracker)

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
        except Exception as error:  # noqa: BLE001 - any error fails the test below
            errors.append(error)

    writer = threading.Thread(target=keep_updating)
    writer.start()

    try:
        client = TestClient(app)
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
def fake_service():
    return FakePollingService()


def test_source_and_recordings_endpoints(fake_service):
    app = make_app(polling=fake_service)
    client = TestClient(app)

    assert client.get("/source").json()["mode"] == "live"
    assert client.get("/recordings").json()[0]["name"] == "session.jsonl"


def test_start_replay_endpoint(fake_service):
    app = make_app(polling=fake_service)
    client = TestClient(app)

    response = client.post(
        "/source/replay", json={"recording": "session.jsonl", "speed": 10}
    )

    assert response.status_code == 200
    assert fake_service.calls == [("replay", "session.jsonl", 10.0, False)]


def test_start_replay_defaults_to_normal_speed(fake_service):
    app = make_app(polling=fake_service)
    TestClient(app).post("/source/replay", json={"recording": "a.jsonl"})

    assert fake_service.calls == [("replay", "a.jsonl", 1.0, False)]


def test_speed_and_live_endpoints(fake_service):
    app = make_app(polling=fake_service)
    client = TestClient(app)

    assert client.post("/source/replay/speed", json={"speed": 30}).status_code == 200
    assert client.post("/source/live").status_code == 200
    assert fake_service.calls == [("speed", 30.0), ("live",)]


@pytest.mark.parametrize("speed", [0, -5, 10_000])
def test_speed_outside_limits_is_rejected(fake_service, speed):
    app = make_app(polling=fake_service)
    response = TestClient(app).post(
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
    app = make_app(polling=FakePollingService(error))

    response = TestClient(app).post(
        "/source/replay", json={"recording": "x.jsonl"}
    )

    assert response.status_code == status


# --- observer endpoints ----------------------------------------------------



class StatsPollingService(FakePollingService):
    def status(self):
        return {
            "mode": "replay", "recording": "a.jsonl", "speed": 5.0,
            "progress": {"position_seconds": 1.0}, "clock": {"now": 1.0, "speed": 5.0},
        }

    def worker_status(self):
        return {"running": True, "queue_depth": 0, "processed": 7, "failed": 0}


@pytest.fixture
def observed():
    """(tracker, app) with real observers and one geofence."""
    tracker = AircraftTracker()
    fences = [{"name": "Here", "longitude": 23.0, "latitude": 40.6, "radius_miles": 5}]
    app = make_app(
        tracker,
        polling=StatsPollingService(),
        observers=attach_default_observers(tracker, fences),
    )
    return tracker, app


def test_stats_endpoint_combines_observers_queue_and_source(observed):
    tracker, app = observed
    tracker.add_aircraft(
        Aircraft("NEARBY", 1000, 23.01, 40.6, 10000, 90.0, "Test", 300.0, 23.0, 40.6)
    )

    stats = TestClient(app).get("/stats").json()

    assert stats["tracker"]["tracked"] == 1
    assert stats["queue"]["processed"] == 7
    assert stats["source"] == {
        "mode": "replay", "recording": "a.jsonl", "speed": 5.0,
        "progress": {"position_seconds": 1.0},
    }
    assert set(stats["prediction_accuracy"]["segments"]) == {"all", "turning", "straight"}


def test_events_and_geofences_endpoints(observed):
    tracker, app = observed
    tracker.add_aircraft(
        Aircraft("NEARBY", 1000, 23.01, 40.6, 10000, 90.0, "Test", 300.0, 23.0, 40.6)
    )
    client = TestClient(app)

    events = client.get("/events").json()
    fences = client.get("/geofences").json()

    assert [(e["type"], e["callsign"]) for e in events] == [("geofence_enter", "NEARBY")]
    assert fences[0]["name"] == "Here"
    assert fences[0]["aircraft_inside"] == ["NEARBY"]
    assert client.get("/events", params={"limit": 0}).status_code == 422


def test_aircraft_endpoint_reports_missing_state(monkeypatch):
    tracker = make_tracker()
    tracker.aircrafts["FAR_FAST"].lifecycle.mark_missing(1015)
    app = make_app(tracker=tracker)

    planes = TestClient(app).get("/aircraft").json()

    assert {plane["callsign"]: plane["state"] for plane in planes} == {
        "NEAR_SLOW": "observed",
        "FAR_FAST": "missing",
    }


# --- app factory -----------------------------------------------------------

def test_each_app_has_its_own_services():
    first, second = make_app(), make_app()
    first.state.services.tracker.add_aircraft(FakeAircraft("ONLY_FIRST", 1.0, 0.0))

    assert [p["callsign"] for p in TestClient(first).get("/aircraft").json()] == ["ONLY_FIRST"]
    assert TestClient(second).get("/aircraft").json() == []


def test_lifespan_builds_and_stops_services(monkeypatch):
    built = []

    class FakeLivePolling(FakePollingService):
        def __init__(self):
            super().__init__()
            self.started = self.stopped = False

        def start(self):
            self.started = True

        def stop(self):
            self.stopped = True

    def fake_build():
        tracker = AircraftTracker()
        services = api.AppServices(
            tracker, FakeLivePolling(), attach_default_observers(tracker, [])
        )
        built.append(services)
        return services

    monkeypatch.setattr(api, "build_services", fake_build)
    app = api.create_app()
    assert app.state.services is None  # nothing exists until startup

    with TestClient(app) as client:
        assert client.get("/aircraft").json() == []
        assert built[0].polling.started

    assert built[0].polling.stopped
    assert len(built) == 1


def test_no_module_level_tracker():
    import main

    assert not hasattr(api, "aircraft_tracker")
    assert not hasattr(main, "aircraft_tracker")


# --- response cap ----------------------------------------------------------

def crowded_tracker(count):
    tracker = AircraftTracker()
    for index in range(count):
        tracker.add_aircraft(FakeAircraft(f"P{index:04d}", float(index), 0.0))
    return tracker


def test_aircraft_response_is_capped_and_reports_the_total():
    app = make_app(tracker=crowded_tracker(config.MAX_AIRCRAFT_PER_RESPONSE + 5))

    response = TestClient(app).get("/aircraft")

    assert config.MAX_AIRCRAFT_PER_RESPONSE == 1000
    assert len(response.json()) == 1000
    assert response.headers["X-Total-Aircraft"] == "1005"
    # The nearest are kept (FakeAircraft distance = its index).
    assert response.json()[-1]["callsign"] == "P0999"


def test_limit_parameter_and_its_bounds():
    client = TestClient(make_app(tracker=crowded_tracker(10)))

    response = client.get("/aircraft", params={"limit": 3})
    assert [p["callsign"] for p in response.json()] == ["P0000", "P0001", "P0002"]
    assert response.headers["X-Total-Aircraft"] == "10"

    assert client.get("/aircraft", params={"limit": 0}).status_code == 422
    assert client.get("/aircraft", params={"limit": 1001}).status_code == 422


def test_total_header_is_readable_by_the_dashboard():
    response = TestClient(make_app()).get(
        "/aircraft", headers={"Origin": "http://localhost:5173"}
    )

    assert "x-total-aircraft" in response.headers["access-control-expose-headers"].lower()
