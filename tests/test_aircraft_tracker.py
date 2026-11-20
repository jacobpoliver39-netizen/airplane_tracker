from aircraft_tracker import AircraftTracker
from ranking_strategies import NearestStrategy, FastestApproachStrategy


class FakeAircraft:
    def __init__(self, callsign, distance):
        self.callsign = callsign
        self.distance = distance

    def get_distance_from_user(self):
        return self.distance


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


def test_sorted_aircrafts_preserves_aircraft_objects():
    tracker = AircraftTracker()
    aircraft = FakeAircraft("TEST123", 10.0)
    tracker.add_aircraft(aircraft)

    sorted_aircraft = tracker.get_sorted_aircrafts()

    assert sorted_aircraft["TEST123"] is aircraft


def test_sorted_aircrafts_with_no_aircraft():
    tracker = AircraftTracker()

    assert tracker.get_sorted_aircrafts() == {}




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
            "UNKNOWN", 5.0, None
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

def test_get_sorted_aircrafts_uses_given_strategy_without_changing_default():
    from ranking_strategies import FastestApproachStrategy, NearestStrategy

    tracker = AircraftTracker()
    tracker.add_aircraft(
        FakeAircraftWithApproachSpeed("FAR_FAST", 30.0, 400.0)
    )
    tracker.add_aircraft(
        FakeAircraftWithApproachSpeed("NEAR_SLOW", 5.0, 100.0)
    )

    ranked = tracker.get_sorted_aircrafts(FastestApproachStrategy())

    assert list(ranked) == ["FAR_FAST", "NEAR_SLOW"]
    assert isinstance(tracker._ranking_strategy, NearestStrategy)
    assert list(tracker.get_sorted_aircrafts()) == ["NEAR_SLOW", "FAR_FAST"]


def test_get_sorted_aircrafts_rejects_invalid_strategy():
    import pytest

    with pytest.raises(TypeError):
        AircraftTracker().get_sorted_aircrafts(object())


def test_tracker_rejects_invalid_ranking_strategy():
    import pytest

    with pytest.raises(TypeError):
        AircraftTracker(ranking_strategy=object())



class FakeAircraftWithPrediction:
    def __init__(self, callsign, distance, straight_nearest, curved_nearest):
        self.callsign = callsign
        self.distance = distance
        self.straight_nearest = straight_nearest
        self.curved_nearest = curved_nearest

    def get_distance_from_user(self):
        return self.distance


class FakePredictor:
    """Returns the nearest approaches stored on FakeAircraftWithPrediction."""

    def nearest_approach(self, aircraft, strategy):
        from prediction_strategies import NearestApproach

        distance = (
            aircraft.curved_nearest if strategy == "curved"
            else aircraft.straight_nearest
        )
        return None if distance is None else NearestApproach(distance, 30.0)


def test_predicted_approach_strategy_ranks_closest_predicted_pass_first():
    from ranking_strategies import NearestPredictedApproachStrategy

    aircrafts = {
        # Nearest now, but flying away: predicted approach = 5 miles.
        "NEAR_LEAVING": FakeAircraftWithPrediction("NEAR_LEAVING", 5.0, 5.0, None),
        # Farther now, but heading almost straight overhead.
        "FAR_OVERHEAD": FakeAircraftWithPrediction("FAR_OVERHEAD", 20.0, 0.5, 0.8),
        "MID_PASSING": FakeAircraftWithPrediction("MID_PASSING", 10.0, 3.0, None),
    }

    ranked = NearestPredictedApproachStrategy(FakePredictor()).sort_aircrafts(aircrafts)

    assert list(ranked) == ["FAR_OVERHEAD", "MID_PASSING", "NEAR_LEAVING"]


def test_predicted_approach_strategy_prefers_curved_over_straight():
    from ranking_strategies import NearestPredictedApproachStrategy

    aircrafts = {
        # Straight line says 1 mile, but the turn takes it 8 miles away.
        "TURNING_AWAY": FakeAircraftWithPrediction("TURNING_AWAY", 10.0, 1.0, 8.0),
        "STRAIGHT": FakeAircraftWithPrediction("STRAIGHT", 10.0, 4.0, None),
    }

    ranked = NearestPredictedApproachStrategy(FakePredictor()).sort_aircrafts(aircrafts)

    assert list(ranked) == ["STRAIGHT", "TURNING_AWAY"]


def test_predicted_approach_strategy_breaks_ties_by_current_distance():
    from ranking_strategies import NearestPredictedApproachStrategy

    aircrafts = {
        "FAR": FakeAircraftWithPrediction("FAR", 30.0, 2.0, None),
        "NEAR": FakeAircraftWithPrediction("NEAR", 10.0, 2.0, None),
    }

    ranked = NearestPredictedApproachStrategy(FakePredictor()).sort_aircrafts(aircrafts)

    assert list(ranked) == ["NEAR", "FAR"]


def test_clear_removes_all_aircraft():
    tracker = AircraftTracker()
    tracker.add_aircraft(FakeAircraft("A", 1.0))
    tracker.add_aircraft(FakeAircraft("B", 2.0))

    tracker.clear()

    assert tracker.aircrafts == {}
