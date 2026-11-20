import pytest

from aircraft import Aircraft
from aircraft_factory import AircraftFactory
from aircraft_tracker import AircraftTracker
from calculator import Calculator
from commands import UpdateAircraftCommand
from observation import AircraftObservation
from prediction_strategies import (
    CTRVPredictionStrategy,
    HistoricalPredictionStrategy,
    MotionState,
    NearestApproach,
    PredictionStrategy,
    StraightLinePredictionStrategy,
)
from trajectory_predictor import PredictionSnapshot, TrajectoryPredictor

PREDICTOR = TrajectoryPredictor()


def test_approach_status_is_approaching_when_future_closest_point_exists():
    aircraft = Aircraft(
        callsign="TESTAPPROACH",
        timestamp=1000,
        longitude=0.0,
        latitude=1.0,
        altitude=10000,
        heading=180.0,
        country_of_origin="Test",
        velocity=100.0,
        user_longitude=0.0,
        user_latitude=0.0,
    )

    assert PREDICTOR.approach_status(aircraft) == "approaching"


def test_approach_status_is_passed_after_distance_starts_increasing():
    from aircraft import Position

    aircraft = Aircraft(
        callsign="TESTPASSED",
        timestamp=1030,
        longitude=0.0,
        latitude=1.0,
        altitude=10000,
        heading=0.0,
        country_of_origin="Test",
        velocity=100.0,
        user_longitude=0.0,
        user_latitude=0.0,
    )

    aircraft.location_history[1000] = Position(
        0.0, 0.0, 3.0, 180.0, 0.0
    )
    aircraft.location_history[1015] = Position(
        0.0, 0.0, 1.0, 180.0, 0.0
    )
    aircraft.location_history[1030] = Position(
        0.0, 0.0, 2.0, 0.0, 180.0
    )
    aircraft.distance_from_user = 2.0

    assert PREDICTOR.approach_status(aircraft) == "passed"
    assert aircraft.get_closest_distance_so_far() == 1.0


def test_approach_status_is_moving_away_when_no_future_approach_exists():
    aircraft = Aircraft(
        callsign="TESTAWAY",
        timestamp=1000,
        longitude=0.0,
        latitude=1.0,
        altitude=10000,
        heading=0.0,
        country_of_origin="Test",
        velocity=100.0,
        user_longitude=0.0,
        user_latitude=0.0,
    )

    assert PREDICTOR.approach_status(aircraft) == "moving_away"

def test_estimated_turn_rate_detects_clockwise_turn():
    aircraft = Aircraft(
        callsign="TESTTURN",
        timestamp=0,
        longitude=0.000,
        latitude=0.000,
        altitude=10000,
        heading=0.0,
        country_of_origin="Test",
        velocity=100.0,
        user_longitude=0.0,
        user_latitude=0.0,
    )

    for timestamp, longitude, latitude in [
        (15, 0.000, 0.010),
        (30, 0.003, 0.020),
        (45, 0.010, 0.027),
    ]:
        aircraft.update_info(
            new_longitude=longitude,
            new_latitude=latitude,
            new_timestamp=timestamp,
            new_altitude=10000,
            new_heading=0.0,
            new_velocity=100.0,
        )

    turn_rate = CTRVPredictionStrategy().estimate_turn_rate(aircraft)

    assert turn_rate is not None
    assert turn_rate > 0


def test_estimated_turn_rate_returns_none_with_one_position():
    aircraft = Aircraft(
        callsign="TESTNOTURN",
        timestamp=1000,
        longitude=0.0,
        latitude=1.0,
        altitude=10000,
        heading=180.0,
        country_of_origin="Test",
        velocity=100.0,
        user_longitude=0.0,
        user_latitude=0.0,
    )

    assert CTRVPredictionStrategy().estimate_turn_rate(aircraft) is None

def test_historical_strategy_fits_eastbound_flight():
    aircraft = Aircraft(
        callsign="TESTGROUND",
        timestamp=1000,
        longitude=0.000,
        latitude=0.000,
        altitude=10000,
        heading=0.0,
        country_of_origin="Test",
        velocity=100.0,
        user_longitude=0.0,
        user_latitude=0.0,
    )

    aircraft.update_info(
        new_longitude=0.010,
        new_latitude=0.000,
        new_timestamp=1015,
        new_altitude=10000,
        new_heading=0.0,
        new_velocity=100.0,
    )

    state = HistoricalPredictionStrategy().initial_state(aircraft)

    assert state is not None
    assert state.speed_mph > 0
    assert state.heading == pytest.approx(90.0)


def test_historical_strategy_needs_history():
    aircraft = Aircraft(
        callsign="TESTNODATA",
        timestamp=1000,
        longitude=0.0,
        latitude=1.0,
        altitude=10000,
        heading=180.0,
        country_of_origin="Test",
        velocity=100.0,
        user_longitude=0.0,
        user_latitude=0.0,
    )

    assert HistoricalPredictionStrategy().initial_state(aircraft) is None

def test_curved_nearest_approach_returns_none_with_insufficient_history():
    aircraft = Aircraft(
        callsign="TEST123",
        timestamp=1000,
        longitude=1.0,
        latitude=0.0,
        altitude=10000,
        heading=270.0,
        country_of_origin="Test",
        velocity=120.0,
        user_longitude=0.0,
        user_latitude=0.0,
    )

    assert PREDICTOR.nearest_approach(aircraft, "curved") is None


def test_curved_nearest_approach_uses_estimated_turn_rate(monkeypatch):
    aircraft = Aircraft(
        callsign="TEST456",
        timestamp=1000,
        longitude=0.01,
        latitude=0.0,
        altitude=10000,
        heading=270.0,
        country_of_origin="Test",
        velocity=120.0,
        user_longitude=0.0,
        user_latitude=0.0,
    )

    monkeypatch.setattr(
        CTRVPredictionStrategy,
        "estimate_turn_rate",
        lambda self, aircraft: 0.5,
    )

    result = PREDICTOR.nearest_approach(aircraft, "curved")

    assert result is not None

    distance, time = result

    # About 0.7 miles east, flying west at 2 miles per minute: the
    # closest point falls inside the 60 s window.
    assert distance < aircraft.distance_from_user
    assert 0 < time < 60


def test_curved_trajectory_returns_none_without_sufficient_history():
    aircraft = Aircraft(
        callsign="TEST123",
        timestamp=1000,
        longitude=1.0,
        latitude=0.0,
        altitude=10000,
        heading=270.0,
        country_of_origin="Test",
        velocity=120.0,
        user_longitude=0.0,
        user_latitude=0.0,
    )

    assert PREDICTOR.trajectory(aircraft, "curved") is None


def test_curved_trajectory_returns_gps_coordinates(monkeypatch):
    aircraft = Aircraft(
        callsign="TEST456",
        timestamp=1000,
        longitude=1.0,
        latitude=0.0,
        altitude=10000,
        heading=270.0,
        country_of_origin="Test",
        velocity=120.0,
        user_longitude=0.0,
        user_latitude=0.0,
    )

    monkeypatch.setattr(
        CTRVPredictionStrategy,
        "estimate_turn_rate",
        lambda self, aircraft: 0.5,
    )

    trajectory = PREDICTOR.trajectory(aircraft, "curved")

    assert trajectory is not None
    assert len(trajectory) == 13

    # First point is the aircraft's current position.
    assert trajectory[0] == [
        aircraft.latitude,
        aircraft.longitude,
    ]

    # Every point is a valid latitude/longitude pair.
    for latitude, longitude in trajectory:
        assert -90 <= latitude <= 90
        assert -180 <= longitude <= 180

    # The aircraft should move from its starting position.
    assert trajectory[-1] != trajectory[0]

def test_straight_trajectory_projects_reported_heading_and_speed():
    aircraft = Aircraft(
        callsign="TEST_STRAIGHT",
        timestamp=1000,
        longitude=0.0,
        latitude=0.0,
        altitude=10000,
        heading=0.0,
        country_of_origin="Test",
        velocity=60.0,
        user_longitude=0.0,
        user_latitude=0.0,
    )

    trajectory = PREDICTOR.trajectory(aircraft, "straight", prediction_seconds=60)
    start, end = trajectory[0], trajectory[-1]

    assert len(trajectory) == 13  # one point every 5 s, 0..60 s

    assert start == [0.0, 0.0]
    # 60 mph for 60 s is one mile north.
    assert Calculator.calculate_haversine_distance(
        0.0, 0.0, end[1], end[0]
    ) == pytest.approx(1.0, abs=0.001)
    assert end[1] == pytest.approx(0.0)


def test_historical_strategy_uses_last_six_positions(monkeypatch):
    aircraft = Aircraft(
        callsign="TEST_WINDOW",
        timestamp=1000,
        longitude=0.0,
        latitude=0.0,
        altitude=10000,
        heading=90.0,
        country_of_origin="Test",
        velocity=100.0,
        user_longitude=0.0,
        user_latitude=0.0,
    )

    for step in range(1, 8):
        aircraft.update_info(
            new_longitude=0.01 * step,
            new_latitude=0.0,
            new_timestamp=1000 + 15 * step,
            new_altitude=10000,
            new_heading=90.0,
            new_velocity=100.0,
        )

    received = []

    def fake_estimate(observations):
        received.append(observations)
        return None

    monkeypatch.setattr(Calculator, "estimate_ground_motion", fake_estimate)

    HistoricalPredictionStrategy().initial_state(aircraft)

    assert len(received[0]) == 6


def make_turning_aircraft():
    """
    Aircraft flying a clockwise circle at 3 deg/s and 300 mph, observed
    every 15 s like the live tracker. The reported heading at each fix
    is the true current track.
    """
    speed, turn_rate, step = 300.0, 3.0, 15
    start_track = 0.0

    def state(t):
        east, north = Calculator.predict_ctrv_position(
            speed, start_track, turn_rate, t
        )
        longitude, latitude = Calculator.local_coordinates_to_gps(
            east, north, 23.0, 40.0
        )
        heading = (start_track + turn_rate * t) % 360
        return longitude, latitude, heading

    longitude, latitude, heading = state(0)
    aircraft = Aircraft(
        "TURNING", 1000, longitude, latitude, 10000, heading,
        "Test", speed, 23.0, 40.6,
    )

    for t in range(step, 6 * step, step):
        longitude, latitude, heading = state(t)
        aircraft.update_info(
            longitude, latitude, 1000 + t, 10000, heading, speed
        )

    return aircraft


def test_curved_trajectory_leaves_along_reported_heading():
    aircraft = make_turning_aircraft()

    trajectory = PREDICTOR.trajectory(aircraft, "curved", sample_interval_seconds=1)
    (lat0, lon0), (lat1, lon1) = trajectory[0], trajectory[1]
    initial_track = Calculator.bearing_angle_from_user_to_plane(
        lon1, lat1, lon0, lat0
    )

    # Over the first second the track turns 3 degrees, so the first
    # segment's bearing is about heading + 1.5. Before the fix it was
    # tens of degrees behind.
    assert abs(
        Calculator.angular_difference(initial_track, aircraft.heading)
    ) < 3


def test_curved_trajectory_follows_the_turn():
    aircraft = make_turning_aircraft()

    turn_rate = CTRVPredictionStrategy().estimate_turn_rate(aircraft)
    trajectory = PREDICTOR.trajectory(aircraft, "curved")

    assert turn_rate == pytest.approx(3.0, abs=0.1)

    # 60 s at 3 deg/s: the final segment points about 180 deg later.
    (lat_a, lon_a), (lat_b, lon_b) = trajectory[-2], trajectory[-1]
    final_track = Calculator.bearing_angle_from_user_to_plane(
        lon_b, lat_b, lon_a, lat_a
    )
    expected = (aircraft.heading + 3.0 * 57.5) % 360

    assert abs(Calculator.angular_difference(final_track, expected)) < 5


# --- strategies and the predictor's registry -----------------------------

def make_aircraft(longitude=0.0, latitude=0.0, heading=90.0, velocity=360.0,
                  timestamp=1000, user_longitude=0.0, user_latitude=0.0):
    return Aircraft(
        "TEST", timestamp, longitude, latitude, 10000, heading,
        "Test", velocity, user_longitude, user_latitude,
    )


def test_default_predictor_has_three_strategies():
    assert PREDICTOR.strategy_names == ["straight", "curved", "historical"]


def test_strategy_lookup_by_name_or_object():
    strategy = StraightLinePredictionStrategy()

    assert isinstance(PREDICTOR.strategy("curved"), CTRVPredictionStrategy)
    assert PREDICTOR.strategy(strategy) is strategy

    with pytest.raises(KeyError):
        PREDICTOR.strategy("teleport")


def test_predictor_rejects_bad_strategy_sets():
    with pytest.raises(TypeError):
        TrajectoryPredictor([object()])

    with pytest.raises(ValueError):
        TrajectoryPredictor(
            [StraightLinePredictionStrategy(), StraightLinePredictionStrategy()]
        )


class StandStillStrategy(PredictionStrategy):
    """A new strategy needs only a name and an initial state."""

    name = "stand_still"

    def initial_state(self, aircraft):
        return MotionState(
            aircraft.timestamp, aircraft.longitude, aircraft.latitude,
            speed_mph=0.0, heading=0.0, turn_rate=0.0,
        )


def test_custom_strategy_plugs_into_trajectories_and_scoring():
    predictor = TrajectoryPredictor([StandStillStrategy()])
    aircraft = make_aircraft()

    trajectory = predictor.trajectory(aircraft, "stand_still")
    assert all(point == [0.0, 0.0] for point in trajectory)

    snapshot = predictor.snapshot(aircraft)
    # One mile east, 10 s later: standing still is one mile wrong.
    longitude, latitude = Calculator.local_coordinates_to_gps(1.0, 0.0, 0.0, 0.0)
    result = predictor.evaluate(snapshot, 1010, longitude, latitude)

    assert result["stand_still_error_miles"] == pytest.approx(1.0, abs=0.001)


def test_trajectory_rejects_invalid_sampling():
    aircraft = make_aircraft()

    assert PREDICTOR.trajectory(aircraft, "straight", prediction_seconds=-1) is None
    assert PREDICTOR.trajectory(aircraft, "straight", sample_interval_seconds=0) is None


# --- straight-line nearest approach --------------------------------------

def test_straight_nearest_approach_passing_abeam():
    # Two miles south of the user... flying north, offset one mile east.
    longitude, latitude = Calculator.local_coordinates_to_gps(1.0, -2.0, 0.0, 0.0)
    aircraft = make_aircraft(longitude, latitude, heading=0.0, velocity=120.0)

    approach = PREDICTOR.nearest_approach(aircraft, "straight")

    assert isinstance(approach, NearestApproach)
    assert approach.distance_miles == pytest.approx(1.0, abs=0.02)
    # Two miles at 2 miles per minute.
    assert approach.time_seconds == pytest.approx(60, abs=2)


def test_straight_nearest_approach_moving_away_is_current_distance():
    longitude, latitude = Calculator.local_coordinates_to_gps(0.0, 3.0, 0.0, 0.0)
    aircraft = make_aircraft(longitude, latitude, heading=0.0)

    approach = PREDICTOR.nearest_approach(aircraft, "straight")

    assert approach.distance_miles == pytest.approx(3.0, abs=0.01)
    assert approach.time_seconds is None


# --- snapshots and scoring -----------------------------------------------

def test_snapshot_has_no_curved_or_historical_state_without_history():
    snapshot = PREDICTOR.snapshot(make_aircraft())

    assert snapshot.timestamp == 1000
    assert snapshot.states["straight"] is not None
    assert snapshot.states["curved"] is None
    assert snapshot.states["historical"] is None


def test_evaluate_measures_straight_line_error():
    snapshot = PREDICTOR.snapshot(make_aircraft())

    # At 360 mph, the aircraft travels one mile east in 10 seconds.
    longitude, latitude = Calculator.local_coordinates_to_gps(1.0, 0.0, 0.0, 0.0)
    result = PREDICTOR.evaluate(snapshot, 1010, longitude, latitude)

    assert result["timestamp"] == 1000
    assert result["elapsed_seconds"] == 10
    assert result["straight_error_miles"] < 0.01
    assert result["curved_error_miles"] is None
    assert result["historical_error_miles"] is None


def test_evaluate_measures_curved_error():
    state = MotionState(1000, 0.0, 0.0, 360.0, 90.0, turn_rate=1.0)
    snapshot = PredictionSnapshot(
        timestamp=1000,
        states={
            "straight": StraightLinePredictionStrategy().initial_state(make_aircraft()),
            "curved": state,
            "historical": None,
        },
    )

    # Generate the actual position with the same CTRV model.
    east, north = Calculator.predict_ctrv_position(360.0, 90.0, 1.0, 10)
    longitude, latitude = Calculator.local_coordinates_to_gps(east, north, 0.0, 0.0)

    result = PREDICTOR.evaluate(snapshot, 1010, longitude, latitude)

    assert result["curved_error_miles"] < 0.01
    assert result["straight_error_miles"] > result["curved_error_miles"]


def test_evaluate_ignores_positions_that_are_not_newer():
    snapshot = PREDICTOR.snapshot(make_aircraft())

    assert PREDICTOR.evaluate(snapshot, 1000, 0.0, 0.0) is None
    assert PREDICTOR.evaluate(snapshot, 990, 0.0, 0.0) is None


def test_historical_strategy_is_scored_once_there_is_history():
    aircraft = make_turning_aircraft()

    snapshot = PREDICTOR.snapshot(aircraft)

    assert snapshot.states["historical"] is not None
    assert snapshot.states["curved"] is not None


# --- scoring through UpdateAircraftCommand -------------------------------

def make_observation(timestamp, longitude):
    return AircraftObservation(
        callsign="TEST_RECORD",
        timestamp=timestamp,
        longitude=longitude,
        latitude=0.0,
        altitude=10000.0,
        on_ground=False,
        velocity=360.0,
        heading=90.0,
        country_of_origin="Test",
    )


def apply(tracker, observation):
    UpdateAircraftCommand(
        observation, AircraftFactory(0.0, 0.0), minimum_altitude=10
    ).execute(tracker)


class RecordingObserver:
    def __init__(self):
        self.updates = []

    def on_aircraft_added(self, aircraft):
        pass

    def on_aircraft_updated(self, aircraft, prediction_result):
        self.updates.append(prediction_result)


def test_update_command_sends_prediction_score_with_update_event():
    tracker = AircraftTracker()
    observer = RecordingObserver()
    tracker.subscribe(observer)

    apply(tracker, make_observation(1000, 0.0))
    apply(tracker, make_observation(1010, 0.001))

    assert len(observer.updates) == 1
    result = observer.updates[0]
    assert result["timestamp"] == 1000
    assert result["elapsed_seconds"] == 10
    assert result["straight_error_miles"] is not None


def test_update_command_does_not_score_a_repeated_timestamp():
    tracker = AircraftTracker()
    observer = RecordingObserver()
    tracker.subscribe(observer)

    apply(tracker, make_observation(1000, 0.0))
    apply(tracker, make_observation(1010, 0.001))
    apply(tracker, make_observation(1010, 0.002))

    # Both updates are announced, but only the newer position is scored.
    assert observer.updates[0] is not None
    assert observer.updates[1] is None


# --- rule: same heading twice means straight flight ------------------------

def make_curving_history(last_headings):
    """
    Positions along a clockwise curve (so the turn-rate estimate is
    non-zero), with the given reported headings for the final fixes.
    """
    headings = [0.0, 10.0, 20.0, 30.0][: 4 - len(last_headings)] + list(last_headings)
    speed, turn_rate = 300.0, 1.0

    def position(t):
        east, north = Calculator.predict_ctrv_position(speed, 0.0, turn_rate, t)
        return Calculator.local_coordinates_to_gps(east, north, 23.0, 40.0)

    longitude, latitude = position(0)
    aircraft = Aircraft(
        "RULE", 1000, longitude, latitude, 10000, headings[0],
        "Test", speed, 23.0, 40.6,
    )
    for index, heading in enumerate(headings[1:], start=1):
        longitude, latitude = position(15 * index)
        aircraft.update_info(longitude, latitude, 1000 + 15 * index, 10000, heading, speed)

    return aircraft


def test_turning_aircraft_gets_a_curved_prediction():
    aircraft = make_curving_history([30.0, 45.0])
    strategy = CTRVPredictionStrategy()

    assert not strategy.heading_unchanged(aircraft)
    assert strategy.estimate_turn_rate(aircraft) is not None
    assert PREDICTOR.trajectory(aircraft, "curved") is not None


def test_same_heading_twice_uses_straight_line_only():
    aircraft = make_curving_history([45.0, 45.0])
    strategy = CTRVPredictionStrategy()

    # The history still says "turning"...
    assert strategy.estimate_turn_rate(aircraft) is not None
    # ...but the reported heading has not changed, so no curve.
    assert strategy.heading_unchanged(aircraft)
    assert strategy.initial_state(aircraft) is None
    assert PREDICTOR.trajectory(aircraft, "curved") is None
    assert PREDICTOR.nearest_approach(aircraft, "curved") is None
    assert PREDICTOR.snapshot(aircraft).states["curved"] is None
    assert PREDICTOR.trajectory(aircraft, "straight") is not None


def test_same_heading_rule_handles_north_wraparound():
    aircraft = make_curving_history([360.0, 0.0])

    assert CTRVPredictionStrategy().heading_unchanged(aircraft)


def test_same_heading_rule_needs_two_positions():
    aircraft = make_aircraft()

    assert not CTRVPredictionStrategy().heading_unchanged(aircraft)


def test_same_heading_rule_only_checks_the_two_latest_reports():
    # Same heading earlier, then a change at the latest report.
    aircraft = make_curving_history([40.0, 40.0, 50.0])

    assert not CTRVPredictionStrategy().heading_unchanged(aircraft)


def test_ranking_falls_back_to_straight_when_heading_unchanged():
    from ranking_strategies import NearestPredictedApproachStrategy

    aircraft = make_curving_history([45.0, 45.0])
    straight = PREDICTOR.nearest_approach(aircraft, "straight")

    assert NearestPredictedApproachStrategy(PREDICTOR).predicted_approach_distance(
        aircraft
    ) == straight.distance_miles
