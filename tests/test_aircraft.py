from aircraft import Aircraft


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

