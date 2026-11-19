"""
Commands that change the tracker.

A command holds only the data it needs (observations, callsigns,
thresholds) and receives the tracker when it is executed. That keeps
commands independent of where they run: the polling thread creates
them, and the tracker worker (command_queue.TrackerWorker) executes
them, or a test executes them directly.
"""

import logging
from abc import ABC, abstractmethod

from aircraft_tracker import AircraftTracker
from observation import AircraftObservation

logger = logging.getLogger(__name__)


class Command(ABC):

    @abstractmethod
    def execute(self, tracker: AircraftTracker) -> None:
        pass


def is_trackable(observation: AircraftObservation, minimum_altitude) -> bool:
    """Return False for aircraft on the ground or below the minimum altitude."""
    if observation.on_ground:
        return False

    return observation.altitude is None or observation.altitude >= minimum_altitude


class UpdateAircraftCommand(Command):
    """
    Apply one observation to the tracker.

    Updates the aircraft if it is already tracked, even when it is now
    low or on the ground, so RemoveLowAltitudeAircraftCommand removes it
    once. Otherwise adds a new aircraft built by the factory, unless it
    is on the ground or below the minimum altitude.
    """

    def __init__(self, observation: AircraftObservation, factory, minimum_altitude):
        self.observation = observation
        self._factory = factory
        self._minimum_altitude = minimum_altitude

    def execute(self, tracker):
        observation = self.observation

        with tracker.lock:
            existing = tracker.aircrafts.get(observation.callsign)

            if existing is not None:
                existing.update_info(
                    observation.longitude,
                    observation.latitude,
                    observation.timestamp,
                    observation.altitude,
                    observation.heading,
                    observation.velocity,
                    new_on_ground=observation.on_ground,
                )
            elif is_trackable(observation, self._minimum_altitude):
                tracker.add_aircraft(self._factory.create(observation))


class RemoveMissingAircraftCommand(Command):
    """
    Remove aircraft that were not in the latest OpenSky response.

    With a current_time and a positive grace_seconds, a missing aircraft
    is only removed once its last position report is older than the
    grace period, so a single missed poll does not drop its history.
    """

    def __init__(
        self,
        observed_callsigns: set[str],
        current_time: float | None = None,
        grace_seconds: float = 0,
    ) -> None:
        self.observed_callsigns = observed_callsigns
        self.current_time = current_time
        self.grace_seconds = grace_seconds

    def execute(self, tracker):
        with tracker.lock:
            missing_callsigns = tracker.aircrafts.keys() - self.observed_callsigns

            for callsign in missing_callsigns:
                if self._is_expired(tracker.aircrafts[callsign]):
                    tracker.remove_aircraft(callsign)

    def _is_expired(self, aircraft):
        if self.current_time is None or self.grace_seconds <= 0:
            return True

        return self.current_time - aircraft.timestamp > self.grace_seconds


class RemoveLowAltitudeAircraftCommand(Command):
    """Remove aircraft on the ground or below a specified minimum altitude."""

    def __init__(self, minimum_altitude=10):
        self.minimum_altitude = minimum_altitude

    def execute(self, tracker):
        with tracker.lock:
            low_altitude_callsigns = [
                callsign
                for callsign, aircraft in tracker.aircrafts.items()
                if self._is_low(aircraft)
            ]

            for callsign in low_altitude_callsigns:
                tracker.remove_aircraft(callsign)

    def _is_low(self, aircraft):
        if getattr(aircraft, "on_ground", False):
            return True

        # An unknown altitude is not evidence of being low.
        return (
            aircraft.altitude is not None
            and aircraft.altitude < self.minimum_altitude
        )


class CommandBatch(Command):
    """
    A list of commands executed in order as one unit (a macro command).

    The tracker lock is held for the whole batch, so the API never sees
    a poll half-applied (e.g. updated but not yet pruned).
    """

    def __init__(self, commands, label="batch"):
        self.commands = list(commands)
        self.label = label

    def __len__(self):
        return len(self.commands)

    def execute(self, tracker):
        with tracker.lock:
            for command in self.commands:
                command.execute(tracker)
