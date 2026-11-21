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

def test_turn_rate_returns_negative_value_for_counterclockwise_turn():
    # A northbound aircraft gradually turns toward the west.
    observations = [
        (0, 0.000, 0.000),
        (15, 0.000, 0.010),
        (30, -0.003, 0.020),
        (45, -0.010, 0.027),
    ]

    rate = Calculator.estimate_turn_rate(observations)

    assert rate is not None
    assert rate < 0

def test_turn_rate_is_stable_with_small_gps_noise_during_straight_flight():
    observations = [
        (0, 0.00000, 0.00000),
        (15, 0.01002, 0.00001),
        (30, 0.01998, -0.00001),
        (45, 0.03001, 0.00001),
        (60, 0.03999, 0.00000),
        (75, 0.05002, -0.00001),
    ]

    rate = Calculator.estimate_turn_rate(observations)

    assert rate is not None
    assert rate == pytest.approx(0.0, abs=0.01)

def test_turn_rate_estimates_known_constant_turn():
    expected_turn_rate = 0.2  # degrees per second
    observations = []

    for elapsed in range(0, 76, 15):
        east, north = Calculator.predict_ctrv_position(
            speed_mph=360,
            ground_track_degrees=0,
            turn_rate_degrees_per_second=expected_turn_rate,
            elapsed_seconds=elapsed,
        )

        longitude, latitude = Calculator.local_coordinates_to_gps(
            east,
            north,
            23.0,
            40.6,
        )

        observations.append((1000 + elapsed, longitude, latitude))

    estimated_rate = Calculator.estimate_turn_rate(observations)

    assert estimated_rate is not None
    assert estimated_rate == pytest.approx(expected_turn_rate, abs=0.02)


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

def test_ground_motion_uses_multiple_observations():
    # Aircraft travels east at approximately 240 mph.
    # The final GPS observation contains a positional deviation.
    observations = [
        (1000, 23.0000, 40.6000),
        (1015, 23.0130, 40.6000),
        (1030, 23.0260, 40.6000),
        (1045, 23.0500, 40.6000),
    ]

    result = Calculator.estimate_ground_motion(observations)

    assert result is not None
    speed, direction = result

    # The earlier observations establish the underlying eastbound motion.
    assert direction == pytest.approx(90.0, abs=0.5)
    assert speed == pytest.approx(164.0, abs=50.0)


def test_haversine_distance_is_not_rounded():
    distance = Calculator.calculate_haversine_distance(
        23.0, 40.6, 23.0001, 40.6
    )

    assert 0 < distance < 0.01
