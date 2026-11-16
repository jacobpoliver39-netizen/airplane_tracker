from abc import ABC, abstractmethod
from aircraft_tracker import AircraftTracker

class Command(ABC):

    @abstractmethod
    def execute(self) -> None:
        pass

class RemoveMissingAircraftCommand(Command):
    """
    Remove aircraft that were not in the latest OpenSky response.

    With a current_time and a positive grace_seconds, a missing aircraft
    is only removed once its last position report is older than the
    grace period, so a single missed poll does not drop its history.
    """

    def __init__(
        self,
        tracker: AircraftTracker,
        observed_callsigns: set[str],
        current_time: float | None = None,
        grace_seconds: float = 0,
    ) -> None:
        self._tracker = tracker
        self._observed_callsigns = observed_callsigns
        self._current_time = current_time
        self._grace_seconds = grace_seconds

    def execute(self):
        with self._tracker.lock:
            missing_callsigns = (
                self._tracker.aircrafts.keys() - self._observed_callsigns
            )

            for callsign in missing_callsigns:
                if self._is_expired(self._tracker.aircrafts[callsign]):
                    self._tracker.remove_aircraft(callsign)

    def _is_expired(self, aircraft):
        if self._current_time is None or self._grace_seconds <= 0:
            return True

        return self._current_time - aircraft.timestamp > self._grace_seconds


class RemoveLowAltitudeAircraftCommand(Command):
    """Remove aircraft on the ground or below a specified minimum altitude."""

    def __init__(self, tracker, minimum_altitude=10):
        self._tracker = tracker
        self._minimum_altitude = minimum_altitude

    def execute(self):
        with self._tracker.lock:
            low_altitude_callsigns = [
                callsign
                for callsign, aircraft in self._tracker.aircrafts.items()
                if self._is_low(aircraft)
            ]

            for callsign in low_altitude_callsigns:
                self._tracker.remove_aircraft(callsign)

    def _is_low(self, aircraft):
        if getattr(aircraft, "on_ground", False):
            return True

        # An unknown altitude is not evidence of being low.
        return (
            aircraft.altitude is not None
            and aircraft.altitude < self._minimum_altitude
        )
