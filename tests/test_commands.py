from aircraft_tracker import AircraftTracker
from commands import RemoveMissingAircraftCommand, RemoveLowAltitudeAircraftCommand

class FakeAircraft:
    def __init__(self, callsign, altitude=30000):
        self.callsign = callsign
        self.altitude = altitude


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
