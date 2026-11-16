from aircraft import Aircraft
from calculator import Calculator
import pytest


def test_update_info_recalculates_bearing_after_aircraft_moves():
    aircraft = Aircraft(
        callsign="TEST123",
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

    # Initially north of the user.
    assert aircraft.bearing_from_user == 0.0

    # Move the aircraft east of the user.
    aircraft.update_info(
        new_longitude=1.0,
        new_latitude=0.0,
        new_timestamp=1015,
        new_altitude=10000,
        new_heading=180.0,
        new_velocity=100.0,
    )

    assert aircraft.bearing_from_user == 90.0


def test_position_history_records_updated_bearing():
    aircraft = Aircraft(
        callsign="TEST456",
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

    aircraft.update_info(
        new_longitude=1.0,
        new_latitude=0.0,
        new_timestamp=1015,
        new_altitude=10000,
        new_heading=180.0,
        new_velocity=100.0,
    )

    latest_position = aircraft.location_history[1015]

    assert latest_position.get_bearing_from_user() == 90.0


def test_approach_speed_with_two_positions():
    aircraft = Aircraft(
        callsign="TEST789",
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

    # Set controlled distances: 2 miles, then 1 mile, 15 seconds later.
    aircraft.location_history[1000].distance_from_user = 2.0

    aircraft.update_info(
        new_longitude=0.0,
        new_latitude=1.0,
        new_timestamp=1015,
        new_altitude=10000,
        new_heading=180.0,
        new_velocity=100.0,
    )
    aircraft.location_history[1015].distance_from_user = 1.0
    aircraft.distance_from_user = 1.0

    assert aircraft.get_approach_speed_towards_user() == 240.0


def test_approach_speed_averages_multiple_intervals():
    aircraft = Aircraft(
        callsign="TEST789",
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

    aircraft.location_history[1000].distance_from_user = 3.0

    aircraft.update_info(
        new_longitude=0.0,
        new_latitude=1.0,
        new_timestamp=1015,
        new_altitude=10000,
        new_heading=180.0,
        new_velocity=100.0,
    )
    aircraft.location_history[1015].distance_from_user = 2.0
    aircraft.distance_from_user = 2.0

    aircraft.update_info(
        new_longitude=0.0,
        new_latitude=1.0,
        new_timestamp=1030,
        new_altitude=10000,
        new_heading=180.0,
        new_velocity=100.0,
    )
    aircraft.location_history[1030].distance_from_user = 1.0
    aircraft.distance_from_user = 1.0

    assert aircraft.get_approach_speed_towards_user() == 240.0

def test_approach_speed_with_one_position_returns_none():
    aircraft = Aircraft(
        callsign="TESTONE",
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

    assert aircraft.get_approach_speed_towards_user() is None


def test_approach_speed_handles_out_of_order_timestamps():
    aircraft = Aircraft(
        callsign="TESTORDER",
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

    aircraft.location_history[1000].distance_from_user = 3.0

    aircraft.update_info(
        new_longitude=0.0,
        new_latitude=1.0,
        new_timestamp=1030,
        new_altitude=10000,
        new_heading=180.0,
        new_velocity=100.0,
    )
    aircraft.location_history[1030].distance_from_user = 1.0

    # Insert an intermediate timestamp after the later timestamp.
    from aircraft import Position
    aircraft.location_history[1015] = Position(
        0.0, 0.0, 2.0, 180.0, 0.0
    )

    assert aircraft.get_approach_speed_towards_user() == 240.0

def test_approach_speed_averages_all_intervals_correctly():
    aircraft = Aircraft(
        callsign="TESTAVG",
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

    # Four positions, each 15 seconds apart.
    # Distances decrease by 0.5, 1.0, and 1.5 miles.
    # Interval speeds: 120, 240, and 360 mph.
    # Expected average: 240 mph.
    aircraft.location_history[1000].distance_from_user = 4.0

    for timestamp, distance in [
        (1015, 3.5),
        (1030, 2.5),
        (1045, 1.0),
    ]:
        aircraft.update_info(
            new_longitude=0.0,
            new_latitude=1.0,
            new_timestamp=timestamp,
            new_altitude=10000,
            new_heading=180.0,
            new_velocity=100.0,
        )
        aircraft.location_history[timestamp].distance_from_user = distance

    aircraft.distance_from_user = 1.0

    assert aircraft.get_approach_speed_towards_user() == 240.0

def test_approach_speed_sorts_positions_by_timestamp():
    aircraft = Aircraft(
        callsign="TESTORDER",
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

    # Insert timestamps out of chronological order.
    aircraft.location_history[1000].distance_from_user = 3.0

    aircraft.update_info(
        new_longitude=0.0,
        new_latitude=1.0,
        new_timestamp=1030,
        new_altitude=10000,
        new_heading=180.0,
        new_velocity=100.0,
    )
    aircraft.location_history[1030].distance_from_user = 1.0

    from aircraft import Position

    aircraft.location_history[1015] = Position(
        longitude=0.0,
        latitude=1.0,
        distance_from_user=2.0,
        heading=180.0,
        bearing_from_user=0.0,
    )

    aircraft.distance_from_user = 1.0

    # Both 15-second intervals represent a 240 mph approach.
    assert aircraft.get_approach_speed_towards_user() == 240.0

def test_approach_speed_is_negative_when_aircraft_moves_away():
    aircraft = Aircraft(
        callsign="TESTAWAY",
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

    aircraft.location_history[1000].distance_from_user = 1.0

    aircraft.update_info(
        new_longitude=0.0,
        new_latitude=1.0,
        new_timestamp=1015,
        new_altitude=10000,
        new_heading=180.0,
        new_velocity=100.0,
    )

    aircraft.location_history[1015].distance_from_user = 2.0
    aircraft.distance_from_user = 2.0

    assert aircraft.get_approach_speed_towards_user() == -240.0


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

    assert aircraft.get_approach_status() == "approaching"


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

    assert aircraft.get_approach_status() == "passed"
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

    assert aircraft.get_approach_status() == "moving_away"

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

    turn_rate = aircraft.get_estimated_turn_rate()

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

    assert aircraft.get_estimated_turn_rate() is None

def test_estimated_ground_motion_detects_eastbound_flight():
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

    result = aircraft.get_estimated_ground_motion()

    assert result is not None

    speed, direction = result

    assert speed > 0
    assert direction == pytest.approx(90.0)


def test_estimated_ground_motion_returns_none_with_one_position():
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

    assert aircraft.get_estimated_ground_motion() is None

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

    assert aircraft.get_curved_nearest_approach() is None


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
        aircraft,
        "get_estimated_turn_rate",
        lambda: 0.5,
    )

    result = aircraft.get_curved_nearest_approach()

    assert result is not None

    distance, time = result

    # About 0.7 miles east, flying west at 2 miles per minute: the
    # closest point falls inside the 60 s window.
    assert distance < aircraft.distance_from_user
    assert 0 < time < 60


def test_get_curved_trajectory_returns_none_without_sufficient_history():
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

    assert aircraft.get_curved_trajectory() is None


def test_get_curved_trajectory_returns_gps_coordinates(monkeypatch):
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
        aircraft,
        "get_estimated_turn_rate",
        lambda: 0.5,
    )

    trajectory = aircraft.get_curved_trajectory()

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

def test_evaluate_prediction_snapshot_measures_straight_line_error():
    aircraft = Aircraft(
        callsign="TEST_EVAL",
        timestamp=1000,
        longitude=0.0,
        latitude=0.0,
        altitude=10000,
        heading=90.0,
        country_of_origin="Test",
        velocity=360.0,
        user_longitude=0.0,
        user_latitude=0.0,
    )

    snapshot = {
        "timestamp": 1000,
        "longitude": 0.0,
        "latitude": 0.0,
        "speed": 360.0,
        "heading": 90.0,
        "turn_rate": None,
    }

    # At 360 mph, the aircraft travels one mile east in 10 seconds.
    actual_longitude, actual_latitude = (
        Calculator.local_coordinates_to_gps(
            1.0, 0.0, 0.0, 0.0
        )
    )

    result = aircraft.evaluate_prediction_snapshot(
        snapshot,
        actual_timestamp=1010,
        actual_longitude=actual_longitude,
        actual_latitude=actual_latitude,
    )

    assert result is not None
    assert result["elapsed_seconds"] == 10
    assert result["straight_error_miles"] < 0.01
    assert result["curved_error_miles"] is None

def test_evaluate_prediction_snapshot_measures_curved_error():
    aircraft = Aircraft(
        callsign="TEST_CURVED_EVAL",
        timestamp=1000,
        longitude=0.0,
        latitude=0.0,
        altitude=10000,
        heading=90.0,
        country_of_origin="Test",
        velocity=360.0,
        user_longitude=0.0,
        user_latitude=0.0,
    )

    snapshot = {
        "timestamp": 1000,
        "longitude": 0.0,
        "latitude": 0.0,
        "speed": 360.0,
        "heading": 90.0,
        "turn_rate": 1.0,
    }

    # Generate the actual position using the same CTRV model.
    east, north = Calculator.predict_ctrv_position(
        360.0,
        90.0,
        1.0,
        10,
    )

    actual_longitude, actual_latitude = (
        Calculator.local_coordinates_to_gps(
            east,
            north,
            0.0,
            0.0,
        )
    )

    result = aircraft.evaluate_prediction_snapshot(
        snapshot,
        actual_timestamp=1010,
        actual_longitude=actual_longitude,
        actual_latitude=actual_latitude,
    )

    assert result is not None
    assert result["elapsed_seconds"] == 10
    assert result["curved_error_miles"] < 0.01
    assert result["straight_error_miles"] > result["curved_error_miles"]

def test_update_info_records_prediction_error():
    aircraft = Aircraft(
        callsign="TEST_RECORD",
        timestamp=1000,
        longitude=0.0,
        latitude=0.0,
        altitude=10000,
        heading=90.0,
        country_of_origin="Test",
        velocity=360.0,
        user_longitude=0.0,
        user_latitude=0.0,
    )

    aircraft.update_info(
        new_longitude=0.001,
        new_latitude=0.0,
        new_timestamp=1010,
        new_altitude=10000,
        new_heading=90.0,
        new_velocity=360.0,
    )

    assert len(aircraft.prediction_errors) == 1

    result = aircraft.prediction_errors[0]

    assert result["timestamp"] == 1000
    assert result["elapsed_seconds"] == 10
    assert result["straight_error_miles"] is not None

def test_update_info_ignores_duplicate_timestamp_for_evaluation():
    aircraft = Aircraft(
        callsign="TEST_DUPLICATE",
        timestamp=1000,
        longitude=0.0,
        latitude=0.0,
        altitude=10000,
        heading=90.0,
        country_of_origin="Test",
        velocity=360.0,
        user_longitude=0.0,
        user_latitude=0.0,
    )

    aircraft.update_info(
        new_longitude=0.001,
        new_latitude=0.0,
        new_timestamp=1010,
        new_altitude=10000,
        new_heading=90.0,
        new_velocity=360.0,
    )

    aircraft.update_info(
        new_longitude=0.002,
        new_latitude=0.0,
        new_timestamp=1010,
        new_altitude=10000,
        new_heading=90.0,
        new_velocity=360.0,
    )

    assert len(aircraft.prediction_errors) == 1



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

    trajectory = aircraft.get_straight_trajectory(prediction_seconds=60)
    start, end = trajectory[0], trajectory[-1]

    assert len(trajectory) == 13  # one point every 5 s, 0..60 s

    assert start == [0.0, 0.0]
    # 60 mph for 60 s is one mile north.
    assert Calculator.calculate_haversine_distance(
        0.0, 0.0, end[1], end[0]
    ) == pytest.approx(1.0, abs=0.001)
    assert end[1] == pytest.approx(0.0)


def test_ground_motion_uses_more_than_two_history_points(monkeypatch):
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

    aircraft.get_estimated_ground_motion()

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

    trajectory = aircraft.get_curved_trajectory(sample_interval_seconds=1)
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

    turn_rate = aircraft.get_estimated_turn_rate()
    trajectory = aircraft.get_curved_trajectory()

    assert turn_rate == pytest.approx(3.0, abs=0.1)

    # 60 s at 3 deg/s: the final segment points about 180 deg later.
    (lat_a, lon_a), (lat_b, lon_b) = trajectory[-2], trajectory[-1]
    final_track = Calculator.bearing_angle_from_user_to_plane(
        lon_b, lat_b, lon_a, lat_a
    )
    expected = (aircraft.heading + 3.0 * 57.5) % 360

    assert abs(Calculator.angular_difference(final_track, expected)) < 5
