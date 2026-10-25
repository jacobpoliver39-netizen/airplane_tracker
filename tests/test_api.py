import api
from fastapi.testclient import TestClient

from aircraft_tracker import AircraftTracker
from ranking_strategies import FastestApproachStrategy


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

    def get_distance_from_user(self):
        return self.distance_from_user

    def get_approach_speed_towards_user(self):
        return self.approach_speed


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
    }
