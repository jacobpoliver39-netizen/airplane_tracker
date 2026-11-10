import pytest

from calculator import Calculator


def test_distance_to_same_coordinates_is_zero():
    distance = Calculator.calculate_haversine_distance(
        23.0, 40.6, 23.0, 40.6
    )

    assert distance == 0.0


def test_one_degree_of_latitude_is_about_69_miles():
    distance = Calculator.calculate_haversine_distance(
        0.0, 0.0, 0.0, 1.0
    )

    assert distance == pytest.approx(69.09, abs=0.02)


@pytest.mark.parametrize(
    ("plane_lon", "plane_lat", "expected_bearing"),
    [
        (0.0, 1.0, 0.0),   # North
        (1.0, 0.0, 90.0),  # East
        (0.0, -1.0, 180.0),  # South
        (-1.0, 0.0, 270.0),  # West
    ],
)
def test_bearing_in_cardinal_directions(
    plane_lon, plane_lat, expected_bearing
):
    bearing = Calculator.bearing_angle_from_user_to_plane(
        plane_lon, plane_lat, 0.0, 0.0
    )

    assert bearing == pytest.approx(expected_bearing)


@pytest.mark.parametrize(
    ("angle", "expected_direction"),
    [
        (0.0, "North"),
        (45.0, "Northeast"),
        (90.0, "East"),
        (135.0, "Southeast"),
        (180.0, "South"),
        (225.0, "Southwest"),
        (270.0, "West"),
        (315.0, "Northwest"),
        (359.0, "North"),
    ],
)
def test_compass_direction(angle, expected_direction):
    assert Calculator.direction_of_plane_from_user(angle) == expected_direction


def test_heading_toward_user_is_classified_as_approaching():
    assert Calculator.approaching(0.0, 180.0) == "Approaching You"


def test_heading_away_from_user_is_classified_as_flying_away():
    assert Calculator.approaching(0.0, 0.0) == "Flying Away From You"


def test_perpendicular_heading_is_classified_correctly():
    assert Calculator.approaching(0.0, 90.0) == (
        "Flying Perpendicular to You"
    )


def test_nearest_approach_is_zero_for_direct_approach():
    assert Calculator.nearest_approach(0.0, 10.0, 180.0) == 0.0


def test_nearest_approach_equals_distance_for_perpendicular_flight():
    assert Calculator.nearest_approach(0.0, 10.0, 90.0) == 10.0


def test_time_to_nearest_approach_for_direct_flight():
    time_seconds = Calculator.nearest_approach_time(
        0.0, 10.0, 180.0, 100.0
    )

    assert time_seconds == 360.0


def test_angular_difference_handles_360_degree_boundary():
    assert Calculator.angular_difference(5, 355) == 10
    assert Calculator.angular_difference(355, 5) == -10


def test_angular_difference_handles_clockwise_turn():
    assert Calculator.angular_difference(100, 90) == 10


def test_angular_difference_handles_counterclockwise_turn():
    assert Calculator.angular_difference(80, 90) == -10


def test_turn_rate_returns_none_with_insufficient_observations():
    observations = [
        (0, 0.0, 0.0),
        (15, 0.01, 0.0),
    ]

    assert Calculator.estimate_turn_rate(observations) is None


def test_turn_rate_returns_none_for_straight_flight():
    # Aircraft travels east along the equator.
    observations = [
        (0, 0.000, 0.0),
        (15, 0.010, 0.0),
        (30, 0.020, 0.0),
        (45, 0.030, 0.0),
    ]

    rate = Calculator.estimate_turn_rate(observations)

    assert rate == pytest.approx(0.0, abs=0.001)


def test_turn_rate_returns_positive_value_for_clockwise_turn():
    # A northbound aircraft gradually turns toward the east.
    observations = [
        (0, 0.000, 0.000),
        (15, 0.000, 0.010),
        (30, 0.003, 0.020),
        (45, 0.010, 0.027),
    ]

    rate = Calculator.estimate_turn_rate(observations)

    assert rate is not None
    assert rate > 0


def test_turn_rate_ignores_excessively_long_observation_gaps():
    observations = [
        (0, 0.000, 0.000),
        (15, 0.000, 0.010),
        (200, 0.010, 0.020),
    ]

    assert Calculator.estimate_turn_rate(observations) is None

def test_ground_motion_detects_eastbound_flight():
    observations = [
        (1000, 0.000, 0.000),
        (1015, 0.010, 0.000),
    ]

    result = Calculator.estimate_ground_motion(observations)

    assert result is not None
    speed, direction = result

    assert speed > 0
    assert direction == pytest.approx(90.0)


def test_ground_motion_detects_northbound_flight():
    observations = [
        (1000, 0.000, 0.000),
        (1015, 0.000, 0.010),
    ]

    result = Calculator.estimate_ground_motion(observations)

    assert result is not None
    speed, direction = result

    assert speed > 0
    assert direction == pytest.approx(0.0)


def test_ground_motion_returns_none_with_insufficient_data():
    observations = [(1000, 0.0, 0.0)]

    assert Calculator.estimate_ground_motion(observations) is None


def test_ground_motion_rejects_excessively_long_gap():
    observations = [
        (1000, 0.000, 0.000),
        (1100, 0.010, 0.000),
    ]

    assert Calculator.estimate_ground_motion(observations) is None


def test_ground_motion_rejects_insignificant_movement():
    observations = [
        (1000, 0.00000, 0.00000),
        (1015, 0.00001, 0.00000),
    ]

    assert Calculator.estimate_ground_motion(observations) is None

def test_ctrv_straight_northbound_motion():
    east, north = Calculator.predict_ctrv_position(
        speed_mph=360,
        ground_track_degrees=0,
        turn_rate_degrees_per_second=0,
        elapsed_seconds=60,
    )

    assert east == pytest.approx(0.0)
    assert north == pytest.approx(6.0)


def test_ctrv_straight_eastbound_motion():
    east, north = Calculator.predict_ctrv_position(
        speed_mph=360,
        ground_track_degrees=90,
        turn_rate_degrees_per_second=0,
        elapsed_seconds=60,
    )

    assert east == pytest.approx(6.0)
    assert north == pytest.approx(0.0)


def test_ctrv_clockwise_turn_produces_eastward_displacement():
    east, north = Calculator.predict_ctrv_position(
        speed_mph=360,
        ground_track_degrees=0,
        turn_rate_degrees_per_second=1,
        elapsed_seconds=90,
    )

    assert east > 0
    assert north > 0


def test_ctrv_counterclockwise_turn_produces_westward_displacement():
    east, north = Calculator.predict_ctrv_position(
        speed_mph=360,
        ground_track_degrees=0,
        turn_rate_degrees_per_second=-1,
        elapsed_seconds=90,
    )

    assert east < 0
    assert north > 0


def test_ctrv_returns_none_for_missing_inputs():
    result = Calculator.predict_ctrv_position(
        speed_mph=None,
        ground_track_degrees=0,
        turn_rate_degrees_per_second=0,
        elapsed_seconds=60,
    )

    assert result is None

def test_ctrv_completes_full_circle_and_returns_to_start():
    speed_mph = 360
    turn_rate_degrees_per_second = 1
    elapsed_seconds = 360

    east, north = Calculator.predict_ctrv_position(
        speed_mph=speed_mph,
        ground_track_degrees=0,
        turn_rate_degrees_per_second=turn_rate_degrees_per_second,
        elapsed_seconds=elapsed_seconds,
    )

    assert east == pytest.approx(0.0, abs=1e-9)
    assert north == pytest.approx(0.0, abs=1e-9)

def test_gps_to_local_coordinates_same_position():
    east, north = Calculator.gps_to_local_coordinates(
        23.0, 40.6, 23.0, 40.6
    )

    assert east == pytest.approx(0.0)
    assert north == pytest.approx(0.0)


def test_gps_to_local_coordinates_east_of_reference():
    east, north = Calculator.gps_to_local_coordinates(
        24.0, 40.6, 23.0, 40.6
    )

    assert east > 0
    assert north == pytest.approx(0.0)


def test_gps_to_local_coordinates_north_of_reference():
    east, north = Calculator.gps_to_local_coordinates(
        23.0, 41.6, 23.0, 40.6
    )

    assert east == pytest.approx(0.0)
    assert north == pytest.approx(69.09, abs=0.1)

def test_nearest_approach_ctrv_straight_toward_reference():
    result = Calculator.nearest_approach_ctrv(
        aircraft_east=0.0,
        aircraft_north=10.0,
        speed_mph=60.0,
        ground_track_degrees=180.0,
        turn_rate_degrees_per_second=0.0,
        prediction_seconds=60,
        sample_interval_seconds=2,
    )

    distance, time = result

    assert distance == pytest.approx(9.0, abs=0.01)
    assert time == 60


def test_nearest_approach_ctrv_straight_past_reference():
    result = Calculator.nearest_approach_ctrv(
        aircraft_east=0.0,
        aircraft_north=0.5,
        speed_mph=120.0,
        ground_track_degrees=0.0,
        turn_rate_degrees_per_second=0.0,
        prediction_seconds=60,
        sample_interval_seconds=2,
    )

    distance, time = result

    assert distance == pytest.approx(0.5, abs=0.01)
    assert time == 0

def test_nearest_approach_ctrv_turning_flight():
    result = Calculator.nearest_approach_ctrv(
        aircraft_east=2.0,
        aircraft_north=0.0,
        speed_mph=120.0,
        ground_track_degrees=270.0,
        turn_rate_degrees_per_second=0.5,
        prediction_seconds=60,
        sample_interval_seconds=2,
    )

    distance, time = result

    assert distance < 2.0
    assert 0 < time <= 60