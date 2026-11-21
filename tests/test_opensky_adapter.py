import pytest

from aircraft_factory import AircraftFactory
from observation import AircraftObservation
from opensky_adapter import OpenSkyAdapter


def make_state(
    callsign="TEST123 ",
    time_position=1000,
    longitude=23.1,
    latitude=40.7,
    baro_altitude=3000.0,
    on_ground=False,
    velocity=200.0,
    heading=90.0,
):
    """Build an OpenSky state array (17 fields, as the API returns)."""
    return [
        "abc123", callsign, "Greece", time_position, time_position,
        longitude, latitude, baro_altitude, on_ground, velocity, heading,
        0.0, None, baro_altitude, "1234", False, 0,
    ]


# --- OpenSkyAdapter.parse_state -----------------------------------------

def test_parse_state_converts_units_and_strips_callsign():
    observation = OpenSkyAdapter.parse_state(make_state())

    assert observation.callsign == "TEST123"
    assert observation.altitude == pytest.approx(9842.5, abs=0.1)
    assert observation.velocity == pytest.approx(447.39, abs=0.01)
    assert observation.heading == 90.0
    assert observation.on_ground is False


@pytest.mark.parametrize(
    "field",
    ["time_position", "longitude", "latitude", "velocity", "heading"],
)
def test_parse_state_skips_state_missing_required_field(field):
    assert OpenSkyAdapter.parse_state(make_state(**{field: None})) is None


@pytest.mark.parametrize("callsign", [None, "", "   ", 42])
def test_parse_state_skips_invalid_callsign(callsign):
    assert OpenSkyAdapter.parse_state(make_state(callsign=callsign)) is None


def test_parse_state_skips_short_or_non_list_state():
    assert OpenSkyAdapter.parse_state(["abc", "TEST"]) is None
    assert OpenSkyAdapter.parse_state("not a state") is None


def test_parse_state_keeps_missing_altitude_as_none():
    observation = OpenSkyAdapter.parse_state(make_state(baro_altitude=None))

    assert observation.altitude is None


def test_parse_state_keeps_zero_velocity():
    observation = OpenSkyAdapter.parse_state(make_state(velocity=0.0))

    assert observation.velocity == 0


@pytest.mark.parametrize(
    "field",
    ["time_position", "longitude", "latitude", "velocity", "heading"],
)
@pytest.mark.parametrize(
    "bad_value", [float("nan"), float("inf"), float("-inf"), True, "23.1"]
)
def test_parse_state_skips_non_finite_or_non_numeric_field(field, bad_value):
    assert OpenSkyAdapter.parse_state(make_state(**{field: bad_value})) is None


@pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), "3000"])
def test_parse_state_treats_invalid_altitude_as_missing(bad_value):
    observation = OpenSkyAdapter.parse_state(make_state(baro_altitude=bad_value))

    assert observation is not None
    assert observation.altitude is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"latitude": 90.1},
        {"latitude": -90.1},
        {"longitude": 180.1},
        {"longitude": -180.1},
        {"velocity": -1.0},
    ],
)
def test_parse_state_skips_out_of_range_values(overrides):
    assert OpenSkyAdapter.parse_state(make_state(**overrides)) is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"latitude": 90.0},
        {"latitude": -90.0},
        {"longitude": 180.0},
        {"longitude": -180.0},
    ],
)
def test_parse_state_accepts_range_boundaries(overrides):
    assert OpenSkyAdapter.parse_state(make_state(**overrides)) is not None


@pytest.mark.parametrize(
    "heading, expected",
    [(0.0, 0.0), (359.5, 359.5), (360.0, 0.0), (450.0, 90.0), (-90.0, 270.0)],
)
def test_parse_state_normalises_heading(heading, expected):
    observation = OpenSkyAdapter.parse_state(make_state(heading=heading))

    assert observation.heading == pytest.approx(expected)


@pytest.mark.parametrize(
    "value, expected",
    [(True, True), (False, False), (None, False), ("false", False), ("true", False), (1, False)],
)
def test_parse_state_only_json_true_means_on_ground(value, expected):
    observation = OpenSkyAdapter.parse_state(make_state(on_ground=value))

    assert observation.on_ground is expected


# --- OpenSkyAdapter.to_observations -------------------------------------

def test_to_observations_skips_bad_states():
    states = [
        make_state(callsign="GOOD1"),
        make_state(callsign="NOPOS", longitude=None),
        "garbage",
    ]

    observations = OpenSkyAdapter().to_observations(states)

    assert [o.callsign for o in observations] == ["GOOD1"]
    assert all(isinstance(o, AircraftObservation) for o in observations)


def test_to_observations_accepts_none():
    assert OpenSkyAdapter().to_observations(None) == []


# --- AircraftFactory -----------------------------------------------------

def test_factory_creates_aircraft_from_observation():
    observation = OpenSkyAdapter.parse_state(make_state())

    aircraft = AircraftFactory(23.0, 40.6).create(observation)

    assert aircraft.callsign == "TEST123"
    assert aircraft.longitude == observation.longitude
    assert aircraft.altitude == observation.altitude
    assert aircraft.velocity == observation.velocity
    assert aircraft.country_of_origin == "Greece"
    assert aircraft.user_longitude == 23.0
    assert aircraft.user_latitude == 40.6
    assert len(aircraft.location_history) == 1


# --- timestamps after the response ----------------------------------------

from config import MAX_TIMESTAMP_AHEAD_SECONDS


def test_states_timestamped_after_the_response_are_dropped():
    states = [
        make_state(callsign="NOW", time_position=1000),
        make_state(callsign="SLIGHTLY_AHEAD", time_position=1000 + MAX_TIMESTAMP_AHEAD_SECONDS),
        make_state(callsign="FUTURE", time_position=1000 + MAX_TIMESTAMP_AHEAD_SECONDS + 1),
    ]

    observations = OpenSkyAdapter().to_observations(states, response_time=1000)

    assert [o.callsign for o in observations] == ["NOW", "SLIGHTLY_AHEAD"]


def test_without_a_response_time_no_state_is_dropped_for_its_time():
    states = [make_state(callsign="FUTURE", time_position=10**10)]

    assert len(OpenSkyAdapter().to_observations(states)) == 1
