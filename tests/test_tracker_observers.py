import pytest

from aircraft import Aircraft
from aircraft_tracker import AircraftTracker
from calculator import Calculator
from commands import RemoveLowAltitudeAircraftCommand, RemoveMissingAircraftCommand
from tracker_observers import (
    ClosestApproachObserver,
    EventLog,
    GeofenceObserver,
    PredictionAccuracyObserver,
    StatisticsObserver,
    TrackerObserver,
    attach_default_observers,
)

USER = (23.0, 40.6)


def aircraft_at(east, north, callsign="TEST", timestamp=1000, altitude=10000):
    """An aircraft east/north miles from the user."""
    longitude, latitude = Calculator.local_coordinates_to_gps(east, north, *USER)
    return Aircraft(
        callsign, timestamp, longitude, latitude, altitude, 90.0,
        "Test", 300.0, *USER,
    )


def move(aircraft, east, north, timestamp):
    longitude, latitude = Calculator.local_coordinates_to_gps(east, north, *USER)
    aircraft.update_info(longitude, latitude, timestamp, aircraft.altitude, 90.0, 300.0)


class RecordingObserver(TrackerObserver):
    def __init__(self):
        self.events = []

    def on_aircraft_added(self, aircraft):
        self.events.append(("added", aircraft.callsign))

    def on_aircraft_updated(self, aircraft, prediction_result):
        self.events.append(("updated", aircraft.callsign, prediction_result))

    def on_aircraft_removed(self, aircraft, reason):
        self.events.append(("removed", aircraft.callsign, reason))

    def on_tracker_cleared(self):
        self.events.append(("cleared",))


class FakeClock:
    def __init__(self, now=0.0):
        self.now = now

    def __call__(self):
        return self.now


# --- tracker as subject ----------------------------------------------------

def test_tracker_notifies_every_event():
    tracker = AircraftTracker()
    observer = RecordingObserver()
    tracker.subscribe(observer)
    plane = aircraft_at(1, 1)

    tracker.add_aircraft(plane)
    tracker.notify_aircraft_updated(plane, {"score": 1})
    tracker.remove_aircraft("TEST", reason="missing")
    tracker.clear()

    assert observer.events == [
        ("added", "TEST"),
        ("updated", "TEST", {"score": 1}),
        ("removed", "TEST", "missing"),
        ("cleared",),
    ]


def test_subscribe_is_idempotent_and_unsubscribe_stops_events():
    tracker = AircraftTracker()
    observer = RecordingObserver()

    tracker.subscribe(observer)
    tracker.subscribe(observer)
    assert tracker.observers == [observer]

    tracker.unsubscribe(observer)
    tracker.add_aircraft(aircraft_at(1, 1))
    assert observer.events == []


def test_failing_observer_does_not_block_others_or_the_change():
    class Broken(TrackerObserver):
        def on_aircraft_added(self, aircraft):
            raise RuntimeError("boom")

    tracker = AircraftTracker()
    good = RecordingObserver()
    tracker.subscribe(Broken())
    tracker.subscribe(good)

    tracker.add_aircraft(aircraft_at(1, 1))

    assert "TEST" in tracker.aircrafts
    assert good.events == [("added", "TEST")]


def test_removal_commands_report_their_reason():
    tracker = AircraftTracker()
    observer = RecordingObserver()
    tracker.subscribe(observer)
    landed = aircraft_at(1, 1, callsign="LANDED")
    landed.on_ground = True
    tracker.add_aircraft(landed)
    tracker.add_aircraft(aircraft_at(1, 1, callsign="LOW", altitude=5))
    tracker.add_aircraft(aircraft_at(1, 1, callsign="GONE"))

    RemoveLowAltitudeAircraftCommand(10).execute(tracker)
    RemoveMissingAircraftCommand(set()).execute(tracker)

    removed = {event[1]: event[2] for event in observer.events if event[0] == "removed"}
    assert removed == {"LANDED": "landed", "LOW": "low_altitude", "GONE": "missing"}


# --- event log -------------------------------------------------------------

def test_event_log_is_newest_first_limited_and_bounded():
    log = EventLog(max_events=3)
    plane = aircraft_at(1, 1)

    for index in range(5):
        log.add("test", plane, index=index)

    recent = log.recent()
    assert [event["index"] for event in recent] == [4, 3, 2]
    assert [event["id"] for event in recent] == [5, 4, 3]
    assert len(log.recent(limit=1)) == 1
    assert recent[0]["callsign"] == "TEST" and recent[0]["time"] == 1000


# --- statistics ------------------------------------------------------------

def test_statistics_counts_and_update_rate():
    clock = FakeClock()
    stats = StatisticsObserver(clock=clock, rate_window_seconds=60)
    a, b = aircraft_at(1, 1, "A"), aircraft_at(1, 1, "B")

    stats.on_aircraft_added(a)
    stats.on_aircraft_added(b)
    stats.on_aircraft_updated(a, None)
    clock.now = 50
    stats.on_aircraft_updated(a, None)
    stats.on_aircraft_removed(b, "missing")

    summary = stats.summary()
    assert summary["tracked"] == 1
    assert summary["peak_tracked"] == 2
    assert summary["distinct_aircraft"] == 2
    assert summary["added"] == 2
    assert summary["updated"] == 2
    assert summary["removed"] == {"missing": 1}
    assert summary["updates_last_minute"] == 2

    clock.now = 100  # the first update is now older than a minute
    assert stats.summary()["updates_last_minute"] == 1


def test_statistics_reset_on_clear():
    stats = StatisticsObserver(clock=FakeClock())
    stats.on_aircraft_added(aircraft_at(1, 1))

    stats.on_tracker_cleared()

    assert stats.summary()["tracked"] == 0
    assert stats.summary()["added"] == 0


# --- prediction accuracy ---------------------------------------------------

def score(straight, curved=None):
    return {
        "timestamp": 1000,
        "elapsed_seconds": 15,
        "straight_error_miles": straight,
        "curved_error_miles": curved,
    }


def test_accuracy_splits_turning_and_straight_flight():
    turn_rates = {"TURNING": 3.0, "STRAIGHT": 0.1, "UNKNOWN": None}
    accuracy = PredictionAccuracyObserver(
        turning_threshold=1.0,
        turn_rate_estimator=lambda aircraft: turn_rates[aircraft.callsign],
    )

    accuracy.on_aircraft_updated(aircraft_at(1, 1, "TURNING"), score(0.5, 0.1))
    accuracy.on_aircraft_updated(aircraft_at(1, 1, "STRAIGHT"), score(0.02, 0.03))
    accuracy.on_aircraft_updated(aircraft_at(1, 1, "UNKNOWN"), score(0.04))
    accuracy.on_aircraft_updated(aircraft_at(1, 1, "TURNING"), None)  # not scored

    summary = accuracy.summary()
    segments = summary["segments"]

    assert summary["scored_updates"] == 3
    assert segments["all"]["straight"]["count"] == 3
    assert segments["all"]["curved"]["count"] == 2  # None errors are skipped
    assert segments["turning"]["straight"]["mean_miles"] == 0.5
    assert segments["turning"]["curved"]["mean_miles"] == 0.1
    assert segments["straight"]["straight"]["median_miles"] == 0.02
    # The unknown turn rate only counts towards "all".
    assert segments["turning"]["straight"]["count"] == 1
    assert segments["straight"]["straight"]["count"] == 1


def test_accuracy_keeps_recent_samples_and_resets():
    accuracy = PredictionAccuracyObserver(
        max_samples=2, turn_rate_estimator=lambda aircraft: None
    )

    for error in (10.0, 1.0, 3.0):
        accuracy.on_aircraft_updated(aircraft_at(1, 1), score(error))

    assert accuracy.summary()["segments"]["all"]["straight"]["mean_miles"] == 2.0

    accuracy.on_tracker_cleared()
    assert accuracy.summary()["segments"]["all"] == {}


# --- geofence --------------------------------------------------------------

def make_fence(log, radius=5.0):
    return GeofenceObserver("Campus", USER[0], USER[1], radius, log)


def test_geofence_reports_enter_and_exit_once():
    log = EventLog()
    fence = make_fence(log)
    plane = aircraft_at(8, 0)

    fence.on_aircraft_added(plane)
    for east, timestamp in ((4, 1015), (2, 1030), (6, 1045), (7, 1060)):
        move(plane, east, 0, timestamp)
        fence.on_aircraft_updated(plane, None)

    events = list(reversed(log.recent()))
    assert [event["type"] for event in events] == ["geofence_enter", "geofence_exit"]
    assert events[0]["geofence"] == "Campus"
    assert events[0]["distance_miles"] == pytest.approx(4.0, abs=0.05)
    assert events[0]["time"] == 1015


def test_geofence_exit_when_removed_inside():
    log = EventLog()
    fence = make_fence(log)
    plane = aircraft_at(1, 1)

    fence.on_aircraft_added(plane)
    assert fence.summary()["aircraft_inside"] == ["TEST"]

    fence.on_aircraft_removed(plane, "landed")

    assert log.recent()[0]["type"] == "geofence_exit"
    assert log.recent()[0]["reason"] == "landed"
    assert fence.summary()["aircraft_inside"] == []


def test_geofence_forgets_aircraft_on_clear():
    fence = make_fence(EventLog())
    fence.on_aircraft_added(aircraft_at(1, 1))

    fence.on_tracker_cleared()

    assert fence.summary()["aircraft_inside"] == []


# --- closest approach ------------------------------------------------------

def fly(observer, plane, path):
    observer.on_aircraft_added(plane)
    for index, (east, north) in enumerate(path, start=1):
        move(plane, east, north, 1000 + 15 * index)
        observer.on_aircraft_updated(plane, None)


def test_closest_approach_reported_when_distance_starts_rising():
    log = EventLog()
    observer = ClosestApproachObserver(log, report_within_miles=10)
    plane = aircraft_at(-6, 2)

    fly(observer, plane, [(-3, 2), (0, 2), (3, 2), (6, 2)])

    events = log.recent()
    assert len(events) == 1
    assert events[0]["type"] == "closest_approach"
    assert events[0]["distance_miles"] == pytest.approx(2.0, abs=0.05)
    assert events[0]["closest_time"] == 1030


def test_far_or_receding_aircraft_are_not_reported():
    log = EventLog()
    observer = ClosestApproachObserver(log, report_within_miles=1)

    fly(observer, aircraft_at(-6, 2, "FAR"), [(0, 2), (6, 2)])
    fly(observer, aircraft_at(1, 1, "AWAY"), [(2, 2), (3, 3)])

    assert log.recent() == []


# --- wiring ----------------------------------------------------------------

def test_default_observers_are_subscribed_and_reset_events_on_clear():
    tracker = AircraftTracker()
    fences = [{"name": "Here", "longitude": USER[0], "latitude": USER[1], "radius_miles": 5}]
    observers = attach_default_observers(tracker, geofences=fences)

    tracker.add_aircraft(aircraft_at(1, 1))

    assert observers.statistics.summary()["tracked"] == 1
    assert observers.geofences[0].summary()["aircraft_inside"] == ["TEST"]
    assert observers.events.recent()[0]["type"] == "geofence_enter"

    tracker.clear()

    assert observers.events.recent() == []
    assert observers.statistics.summary()["tracked"] == 0
