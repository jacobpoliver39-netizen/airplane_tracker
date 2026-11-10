from aircraft import Aircraft
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

def test_approach_speed_with_one_position_returns_not_enough_data():
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

    assert aircraft.get_approach_speed_towards_user() == "Not Enough Data"


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


def test_curved_nearest_approach_uses_estimated_ground_motion(monkeypatch):
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
        "get_estimated_ground_motion",
        lambda: (120.0, 270.0),
    )
    monkeypatch.setattr(
        aircraft,
        "get_estimated_turn_rate",
        lambda: 0.5,
    )

    result = aircraft.get_curved_nearest_approach()

    assert result is not None

    distance, time = result

    assert distance < aircraft.distance_from_user
    assert 0 <= time <= 60


