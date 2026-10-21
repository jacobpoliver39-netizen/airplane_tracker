from aircraft_tracker import AircraftTracker
from ranking_strategies import NearestStrategy, FastestApproachStrategy


class FakeAircraft:
    def __init__(self, callsign, distance):
        self.callsign = callsign
        self.distance = distance

    def get_distance_from_user(self):
        return self.distance

    def get_info(self):
        return [("Callsign: ", self.callsign)]


def test_sort_aircrafts_by_distance_nearest_first():
    tracker = AircraftTracker()
    tracker.add_aircraft(FakeAircraft("FAR123", 30.0))
    tracker.add_aircraft(FakeAircraft("NEAR123", 5.0))
    tracker.add_aircraft(FakeAircraft("MID123", 15.0))

    sorted_aircraft = tracker.get_sorted_aircrafts()

    assert list(sorted_aircraft.keys()) == [
        "NEAR123",
        "MID123",
        "FAR123",
    ]


def test_sort_aircrafts_by_distance_preserves_aircraft_objects():
    tracker = AircraftTracker()
    aircraft = FakeAircraft("TEST123", 10.0)
    tracker.add_aircraft(aircraft)

    sorted_aircraft = tracker.sort_aircrafts_by_distance()

    assert sorted_aircraft["TEST123"] is aircraft


def test_sort_aircrafts_by_distance_with_no_aircraft():
    tracker = AircraftTracker()

    assert tracker.sort_aircrafts_by_distance() == {}




class FakeAircraftWithApproachSpeed(FakeAircraft):
    def __init__(self, callsign, distance, approach_speed):
        super().__init__(callsign, distance)
        self.approach_speed = approach_speed

    def get_approach_speed_towards_user(self):
        return self.approach_speed


def test_nearest_strategy_ranks_aircraft_by_distance():
    aircrafts = {
        "FAR123": FakeAircraft("FAR123", 30.0),
        "NEAR123": FakeAircraft("NEAR123", 5.0),
        "MID123": FakeAircraft("MID123", 15.0),
    }

    sorted_aircraft = NearestStrategy().sort_aircrafts(aircrafts)

    assert list(sorted_aircraft) == ["NEAR123", "MID123", "FAR123"]


def test_fastest_approach_strategy_ranks_highest_speed_first():
    aircrafts = {
        "SLOW123": FakeAircraftWithApproachSpeed("SLOW123", 10.0, 100.0),
        "FAST123": FakeAircraftWithApproachSpeed("FAST123", 20.0, 400.0),
        "AWAY123": FakeAircraftWithApproachSpeed("AWAY123", 5.0, -50.0),
    }

    sorted_aircraft = FastestApproachStrategy().sort_aircrafts(aircrafts)

    assert list(sorted_aircraft) == ["FAST123", "SLOW123", "AWAY123"]


def test_fastest_approach_strategy_ranks_missing_data_last():
    aircrafts = {
        "UNKNOWN": FakeAircraftWithApproachSpeed(
            "UNKNOWN", 5.0, "Not Enough Data"
        ),
        "KNOWN": FakeAircraftWithApproachSpeed("KNOWN", 10.0, 120.0),
    }

    sorted_aircraft = FastestApproachStrategy().sort_aircrafts(aircrafts)

    assert list(sorted_aircraft) == ["KNOWN", "UNKNOWN"]


def test_tracker_defaults_to_nearest_strategy():
    from ranking_strategies import NearestStrategy

    tracker = AircraftTracker()

    assert isinstance(tracker._ranking_strategy, NearestStrategy)


def test_tracker_can_switch_ranking_strategies():
    from ranking_strategies import FastestApproachStrategy

    tracker = AircraftTracker()
    tracker.add_aircraft(
        FakeAircraftWithApproachSpeed("FAR_FAST", 30.0, 400.0)
    )
    tracker.add_aircraft(
        FakeAircraftWithApproachSpeed("NEAR_SLOW", 5.0, 100.0)
    )

    tracker.set_ranking_strategy(FastestApproachStrategy())

    sorted_aircraft = tracker.get_sorted_aircrafts()

    assert list(sorted_aircraft) == ["FAR_FAST", "NEAR_SLOW"]

def test_tracker_rejects_invalid_ranking_strategy():
    import pytest

    with pytest.raises(TypeError):
        AircraftTracker(ranking_strategy=object())

