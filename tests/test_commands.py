from aircraft_tracker import AircraftTracker
from commands import RemoveMissingAircraftCommand, RemoveLowAltitudeAircraftCommand

class FakeAircraft:
    def __init__(self, callsign, altitude=30000, timestamp=1000, on_ground=False):
        self.callsign = callsign
        self.altitude = altitude
        self.timestamp = timestamp
        self.on_ground = on_ground


def make_tracker(callsigns):
    tracker = AircraftTracker()
    for callsign in callsigns:
        tracker.add_aircraft(FakeAircraft(callsign))
    return tracker


def test_removes_aircraft_missing_from_latest_response():
    tracker = make_tracker(["AAL123", "DAL456", "UAL789"])
    command = RemoveMissingAircraftCommand(
        tracker, {"AAL123", "UAL789"}
    )

    command.execute()

    assert set(tracker.aircrafts) == {"AAL123", "UAL789"}

def test_keeps_all_aircraft_when_all_are_observed():
    tracker = make_tracker(["AAL123", "DAL456"])
    command = RemoveMissingAircraftCommand(tracker, {"AAL123", "DAL456"})

    command.execute()

    assert set(tracker.aircrafts) == {"AAL123", "DAL456"}

def test_removes_aircraft_with_altitude_less_than_ten_feet():
    tracker = AircraftTracker()
    tracker.add_aircraft(FakeAircraft("AAL123", altitude=30000))
    tracker.add_aircraft(FakeAircraft("DAL456", altitude=5))
    tracker.add_aircraft(FakeAircraft("UAL789", altitude=9))

    command = RemoveLowAltitudeAircraftCommand(tracker)
    command.execute()

    assert set(tracker.aircrafts) == {"AAL123"}

def test_aircraft_at_ten_feet_remains():
    tracker = AircraftTracker()
    tracker.add_aircraft(FakeAircraft("AAL123", altitude=10))

    command = RemoveLowAltitudeAircraftCommand(tracker)
    command.execute()

    assert set(tracker.aircrafts) == {"AAL123"}

def test_aircraft_at_nine_feet_removed():
    tracker = AircraftTracker()
    tracker.add_aircraft(FakeAircraft("AAL123", altitude=9))
    tracker.add_aircraft(FakeAircraft("DAL321", altitude=10))
    
    command = RemoveLowAltitudeAircraftCommand(tracker)
    command.execute()

    assert set(tracker.aircrafts) == {"DAL321"}


def test_missing_aircraft_kept_within_grace_period():
    tracker = AircraftTracker()
    tracker.add_aircraft(FakeAircraft("RECENT", timestamp=1000))
    tracker.add_aircraft(FakeAircraft("STALE", timestamp=900))

    RemoveMissingAircraftCommand(
        tracker, set(), current_time=1030, grace_seconds=45
    ).execute()

    assert set(tracker.aircrafts) == {"RECENT"}


def test_observed_aircraft_never_removed_by_grace_check():
    tracker = AircraftTracker()
    tracker.add_aircraft(FakeAircraft("OLD_BUT_SEEN", timestamp=0))

    RemoveMissingAircraftCommand(
        tracker, {"OLD_BUT_SEEN"}, current_time=1000, grace_seconds=45
    ).execute()

    assert set(tracker.aircrafts) == {"OLD_BUT_SEEN"}


def test_removes_aircraft_on_the_ground():
    tracker = AircraftTracker()
    tracker.add_aircraft(FakeAircraft("LANDED", altitude=None, on_ground=True))
    tracker.add_aircraft(FakeAircraft("FLYING", altitude=30000))

    RemoveLowAltitudeAircraftCommand(tracker).execute()

    assert set(tracker.aircrafts) == {"FLYING"}


def test_unknown_altitude_is_not_treated_as_low():
    tracker = AircraftTracker()
    tracker.add_aircraft(FakeAircraft("NO_ALT", altitude=None))

    RemoveLowAltitudeAircraftCommand(tracker).execute()

    assert set(tracker.aircrafts) == {"NO_ALT"}
