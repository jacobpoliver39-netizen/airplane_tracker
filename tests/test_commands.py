from aircraft_state import AircraftLifecycle
from aircraft_tracker import AircraftTracker
from commands import RemoveMissingAircraftCommand, RemoveLowAltitudeAircraftCommand

class FakeAircraft:
    def __init__(self, callsign, altitude=30000, timestamp=1000, on_ground=False):
        self.callsign = callsign
        self.lifecycle = AircraftLifecycle(callsign)
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
        {"AAL123", "UAL789"}
    )

    command.execute(tracker)

    assert set(tracker.aircrafts) == {"AAL123", "UAL789"}

def test_keeps_all_aircraft_when_all_are_observed():
    tracker = make_tracker(["AAL123", "DAL456"])
    command = RemoveMissingAircraftCommand(
        {"AAL123", "DAL456"})

    command.execute(tracker)

    assert set(tracker.aircrafts) == {"AAL123", "DAL456"}

def test_removes_aircraft_with_altitude_less_than_ten_feet():
    tracker = AircraftTracker()
    tracker.add_aircraft(FakeAircraft("AAL123", altitude=30000))
    tracker.add_aircraft(FakeAircraft("DAL456", altitude=5))
    tracker.add_aircraft(FakeAircraft("UAL789", altitude=9))

    command = RemoveLowAltitudeAircraftCommand()
    command.execute(tracker)

    assert set(tracker.aircrafts) == {"AAL123"}

def test_aircraft_at_ten_feet_remains():
    tracker = AircraftTracker()
    tracker.add_aircraft(FakeAircraft("AAL123", altitude=10))

    command = RemoveLowAltitudeAircraftCommand()
    command.execute(tracker)

    assert set(tracker.aircrafts) == {"AAL123"}

def test_aircraft_at_nine_feet_removed():
    tracker = AircraftTracker()
    tracker.add_aircraft(FakeAircraft("AAL123", altitude=9))
    tracker.add_aircraft(FakeAircraft("DAL321", altitude=10))
    
    command = RemoveLowAltitudeAircraftCommand()
    command.execute(tracker)

    assert set(tracker.aircrafts) == {"DAL321"}


def test_missing_aircraft_kept_within_grace_period():
    tracker = AircraftTracker()
    tracker.add_aircraft(FakeAircraft("RECENT", timestamp=1000))
    tracker.add_aircraft(FakeAircraft("STALE", timestamp=900))

    RemoveMissingAircraftCommand(
        set(), current_time=1030, grace_seconds=45
    ).execute(tracker)

    assert set(tracker.aircrafts) == {"RECENT"}


def test_observed_aircraft_never_removed_by_grace_check():
    tracker = AircraftTracker()
    tracker.add_aircraft(FakeAircraft("OLD_BUT_SEEN", timestamp=0))

    RemoveMissingAircraftCommand(
        {"OLD_BUT_SEEN"}, current_time=1000, grace_seconds=45
    ).execute(tracker)

    assert set(tracker.aircrafts) == {"OLD_BUT_SEEN"}


def test_removes_aircraft_on_the_ground():
    tracker = AircraftTracker()
    tracker.add_aircraft(FakeAircraft("LANDED", altitude=None, on_ground=True))
    tracker.add_aircraft(FakeAircraft("FLYING", altitude=30000))

    RemoveLowAltitudeAircraftCommand().execute(tracker)

    assert set(tracker.aircrafts) == {"FLYING"}


def test_unknown_altitude_is_not_treated_as_low():
    tracker = AircraftTracker()
    tracker.add_aircraft(FakeAircraft("NO_ALT", altitude=None))

    RemoveLowAltitudeAircraftCommand().execute(tracker)

    assert set(tracker.aircrafts) == {"NO_ALT"}


# --- UpdateAircraftCommand -----------------------------------------------

from aircraft_factory import AircraftFactory
from commands import CommandBatch, UpdateAircraftCommand
from observation import AircraftObservation


def make_observation(callsign="TEST123", timestamp=1000, longitude=23.1,
                     altitude=10000.0, on_ground=False):
    return AircraftObservation(
        callsign=callsign,
        timestamp=timestamp,
        longitude=longitude,
        latitude=40.7,
        altitude=altitude,
        on_ground=on_ground,
        velocity=400.0,
        heading=90.0,
        country_of_origin="Greece",
    )


def make_update(observation, minimum_altitude=10):
    return UpdateAircraftCommand(
        observation, AircraftFactory(23.0, 40.6), minimum_altitude
    )


def test_update_command_adds_new_aircraft():
    tracker = AircraftTracker()

    make_update(make_observation()).execute(tracker)

    aircraft = tracker.aircrafts["TEST123"]
    assert aircraft.longitude == 23.1
    assert aircraft.user_longitude == 23.0


def test_update_command_updates_existing_aircraft():
    tracker = AircraftTracker()
    make_update(make_observation(timestamp=1000)).execute(tracker)
    original = tracker.aircrafts["TEST123"]

    make_update(make_observation(timestamp=1015, longitude=23.2)).execute(tracker)

    assert tracker.aircrafts["TEST123"] is original
    assert original.longitude == 23.2
    assert len(original.location_history) == 2


def test_update_command_does_not_add_low_or_grounded_aircraft():
    tracker = AircraftTracker()

    make_update(make_observation(callsign="LOW", altitude=5)).execute(tracker)
    make_update(
        make_observation(callsign="GROUND", altitude=None, on_ground=True)
    ).execute(tracker)

    assert tracker.aircrafts == {}


def test_update_command_still_updates_tracked_aircraft_that_lands():
    tracker = AircraftTracker()
    make_update(make_observation(timestamp=1000)).execute(tracker)

    make_update(
        make_observation(timestamp=1015, altitude=None, on_ground=True)
    ).execute(tracker)

    # Updated (not ignored), so the low-altitude command can remove it.
    assert tracker.aircrafts["TEST123"].on_ground is True


# --- CommandBatch --------------------------------------------------------

class RecordingCommand:
    def __init__(self, name, log):
        self.name = name
        self.log = log

    def execute(self, tracker):
        # The batch holds the lock for every command it runs.
        assert tracker.lock._is_owned()
        self.log.append(self.name)


def test_batch_runs_commands_in_order_holding_the_lock():
    log = []
    batch = CommandBatch(
        [RecordingCommand(name, log) for name in ("a", "b", "c")]
    )

    batch.execute(AircraftTracker())

    assert log == ["a", "b", "c"]
    assert len(batch) == 3


def test_batch_update_then_removal_is_applied_together():
    tracker = AircraftTracker()
    make_update(make_observation(timestamp=1000)).execute(tracker)

    CommandBatch([
        make_update(
            make_observation(timestamp=1015, altitude=None, on_ground=True)
        ),
        RemoveLowAltitudeAircraftCommand(),
    ]).execute(tracker)

    assert tracker.aircrafts == {}


def test_update_command_ignores_an_older_report_without_announcing_it():
    tracker = AircraftTracker()
    updates = []

    class Recorder:
        def on_aircraft_added(self, aircraft):
            pass

        def on_aircraft_updated(self, aircraft, prediction_result):
            updates.append(aircraft.timestamp)

    tracker.subscribe(Recorder())
    make_update(make_observation(timestamp=1000)).execute(tracker)
    tracker.aircrafts["TEST123"].lifecycle.mark_missing(1015)

    make_update(make_observation(timestamp=990, longitude=22.0)).execute(tracker)

    aircraft = tracker.aircrafts["TEST123"]
    assert aircraft.timestamp == 1000 and aircraft.longitude == 23.1
    assert updates == []
    # It was in the response, so it is no longer missing.
    assert aircraft.lifecycle.name == "observed"
