from abc import ABC, abstractmethod
from aircraft_tracker import AircraftTracker

class Command(ABC):

    @abstractmethod
    def execute(self) -> None:
        pass

class RemoveMissingAircraftCommand(Command):

    def __init__(self, tracker: AircraftTracker, observed_callsigns: set[str]) -> None:
        self._tracker = tracker
        self._observed_callsigns = observed_callsigns

    def execute(self):
        missing_callsigns = (self._tracker.aircrafts.keys() - self._observed_callsigns)
        for callsign in missing_callsigns:
            self._tracker.remove_aircraft(callsign)


class RemoveLowAltitudeAircraftCommand(Command):
    """Remove aircraft with altitude below a specified minimum."""

    def __init__(self, tracker, minimum_altitude=10):
        self._tracker = tracker
        self._minimum_altitude = minimum_altitude

    def execute(self):
        low_altitude_callsigns = [
            callsign
            for callsign, aircraft in self._tracker.aircrafts.items()
            if aircraft.altitude < self._minimum_altitude
        ]

        for callsign in low_altitude_callsigns:
            self._tracker.remove_aircraft(callsign)
        