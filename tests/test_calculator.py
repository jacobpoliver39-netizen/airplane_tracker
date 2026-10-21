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
