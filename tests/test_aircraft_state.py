import pytest

import main
from aircraft import Aircraft
from aircraft_state import (
    AircraftLifecycle,
    AircraftRemovedError,
    MissingState,
    ObservedState,
    RemovedState,
)
from aircraft_tracker import AircraftTracker
from commands import RemoveMissingAircraftCommand


def make_aircraft(callsign="TEST", timestamp=1000):
    return Aircraft(
        callsign, timestamp, 23.1, 40.7, 10000, 90.0, "Test", 300.0, 23.0, 40.6
    )


def make_state(callsign="TEST123 ", time_position=1000, longitude=23.1):
    return [
        "abc123", callsign, "Greece", time_position, time_position,
        longitude, 40.7, 3000.0, False, 200.0, 90.0,
        0.0, None, 3000.0, "1234", False, 0,
    ]


# --- transitions -----------------------------------------------------------

def test_new_aircraft_is_observed():
    lifecycle = AircraftLifecycle("TEST")

    assert isinstance(lifecycle.state, ObservedState)
    assert lifecycle.name == "observed"
    assert not lifecycle.is_removed


def test_missing_then_observed_again():
    lifecycle = AircraftLifecycle("TEST")

    lifecycle.mark_missing(poll_time=1015)
    assert lifecycle.name == "missing"
    assert lifecycle.state.since == 1015

    lifecycle.mark_observed()
    assert lifecycle.name == "observed"


def test_missing_keeps_the_time_it_first_went_missing():
    lifecycle = AircraftLifecycle("TEST")

    lifecycle.mark_missing(poll_time=1015)
    lifecycle.mark_missing(poll_time=1030)

    assert lifecycle.state.since == 1015


@pytest.mark.parametrize("missing_first", [False, True])
def test_removed_from_observed_or_missing(missing_first):
    lifecycle = AircraftLifecycle("TEST")
    if missing_first:
        lifecycle.mark_missing(1015)

    lifecycle.mark_removed("landed")

    assert isinstance(lifecycle.state, RemovedState)
    assert lifecycle.state.reason == "landed"
    assert lifecycle.is_removed


@pytest.mark.parametrize(
    "transition",
    [
        lambda lifecycle: lifecycle.mark_observed(),
        lambda lifecycle: lifecycle.mark_missing(2000),
        lambda lifecycle: lifecycle.mark_removed("again"),
    ],
    ids=["observed", "missing", "removed"],
)
def test_removed_is_final(transition):
    lifecycle = AircraftLifecycle("TEST")
    lifecycle.mark_removed("missing")
    removed_state = lifecycle.state

    with pytest.raises(AircraftRemovedError):
        transition(lifecycle)

    assert lifecycle.state is removed_state
    assert lifecycle.state.reason == "missing"


# --- expiry ----------------------------------------------------------------

def test_observed_never_expires():
    aircraft = make_aircraft(timestamp=0)

    assert not ObservedState().is_expired(aircraft, 10_000, 45)


@pytest.mark.parametrize(
    "current_time, grace, expired",
    [
        (1030, 45, False),   # inside the grace period
        (1046, 45, True),    # last position older than the grace period
        (None, 45, True),    # no time: missing means gone
        (1030, 0, True),     # no grace period
    ],
)
def test_missing_expires_after_grace_period(current_time, grace, expired):
    aircraft = make_aircraft(timestamp=1000)

    assert MissingState(since=1015).is_expired(aircraft, current_time, grace) is expired


# --- aircraft and tracker --------------------------------------------------

def test_removed_aircraft_refuses_updates():
    tracker = AircraftTracker()
    aircraft = make_aircraft()
    tracker.add_aircraft(aircraft)

    tracker.remove_aircraft("TEST", reason="missing")

    with pytest.raises(AircraftRemovedError):
        aircraft.update_info(23.2, 40.7, 1015, 10000, 90.0, 300.0)

    assert aircraft.longitude == 23.1
    assert aircraft.timestamp == 1000
    assert aircraft.lifecycle.name == "removed"


def test_clear_removes_every_aircraft_for_good():
    tracker = AircraftTracker()
    planes = [make_aircraft("A"), make_aircraft("B")]
    for plane in planes:
        tracker.add_aircraft(plane)

    tracker.clear()

    assert all(plane.lifecycle.is_removed for plane in planes)
    assert {plane.lifecycle.state.reason for plane in planes} == {"cleared"}


def test_missing_command_marks_missing_inside_grace_period():
    tracker = AircraftTracker()
    tracker.add_aircraft(make_aircraft(timestamp=1000))

    RemoveMissingAircraftCommand(set(), current_time=1030, grace_seconds=45).execute(tracker)

    assert tracker.aircrafts["TEST"].lifecycle.name == "missing"


# --- through the polling pipeline ------------------------------------------

def test_aircraft_goes_missing_then_returns():
    tracker = AircraftTracker()
    main.apply_states(tracker, [make_state(time_position=1000)], 1000)

    main.apply_states(tracker, [], 1015)
    plane = tracker.aircrafts["TEST123"]
    assert plane.lifecycle.name == "missing"

    main.apply_states(tracker, [make_state(time_position=1030, longitude=23.2)], 1030)
    assert tracker.aircrafts["TEST123"] is plane
    assert plane.lifecycle.name == "observed"


def test_same_callsign_after_removal_is_a_new_aircraft():
    tracker = AircraftTracker()
    main.apply_states(tracker, [make_state(time_position=1000)], 1000)
    old = tracker.aircrafts["TEST123"]

    # Missing long enough to be removed.
    main.apply_states(tracker, [], 1000 + main.config.MISSING_AIRCRAFT_GRACE_SECONDS + 1)
    assert tracker.aircrafts == {}
    assert old.lifecycle.is_removed

    main.apply_states(tracker, [make_state(time_position=2000)], 2000)
    new = tracker.aircrafts["TEST123"]

    assert new is not old
    assert new.lifecycle.name == "observed"
    assert old.lifecycle.is_removed  # the old object stays removed
    assert len(new.location_history) == 1
