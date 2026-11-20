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
from trajectory_predictor import DEFAULT_PREDICTOR

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

    For a newer position, the predictor first snapshots each strategy's
    prediction from the old state, then scores it against the new
    position. The tracker then tells its observers about the update,
    with that score (PredictionAccuracyObserver collects them).
    """

    def __init__(
        self,
        observation: AircraftObservation,
        factory,
        minimum_altitude,
        predictor=DEFAULT_PREDICTOR,
    ):
        self.observation = observation
        self._factory = factory
        self._minimum_altitude = minimum_altitude
        self._predictor = predictor

    def execute(self, tracker):
        observation = self.observation

        with tracker.lock:
            existing = tracker.aircrafts.get(observation.callsign)

            if existing is not None:
                snapshot = (
                    self._predictor.snapshot(existing)
                    if observation.timestamp > existing.timestamp
                    else None
                )

                applied = existing.update_info(
                    observation.longitude,
                    observation.latitude,
                    observation.timestamp,
                    observation.altitude,
                    observation.heading,
                    observation.velocity,
                    new_on_ground=observation.on_ground,
                )
                # It was in the response, so it is observed (back from
                # missing, if it had dropped out of a poll).
                existing.lifecycle.mark_observed()

                if not applied:
                    # An older report than the current position: nothing
                    # changed, so there is nothing to announce or score.
                    return

                tracker.notify_aircraft_updated(
                    existing,
                    self._score(snapshot) if snapshot is not None else None,
                )
            elif is_trackable(observation, self._minimum_altitude):
                tracker.add_aircraft(self._factory.create(observation))


    def _score(self, snapshot):
        return self._predictor.evaluate(
            snapshot,
            actual_timestamp=self.observation.timestamp,
            actual_longitude=self.observation.longitude,
            actual_latitude=self.observation.latitude,
        )


class RemoveMissingAircraftCommand(Command):
    """
    Mark aircraft that were not in the latest OpenSky response as
    missing, and remove those whose state says they have expired.

    With a current_time and a positive grace_seconds, a missing aircraft
    is only removed once its last position report is older than the
    grace period (MissingState.is_expired), so a single missed poll does
    not drop its history.
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
                lifecycle = tracker.aircrafts[callsign].lifecycle
                lifecycle.mark_missing(self.current_time)

                if lifecycle.is_expired(
                    tracker.aircrafts[callsign],
                    self.current_time,
                    self.grace_seconds,
                ):
                    tracker.remove_aircraft(callsign, reason="missing")


class RemoveLowAltitudeAircraftCommand(Command):
    """Remove aircraft on the ground or below a specified minimum altitude."""

    def __init__(self, minimum_altitude=10):
        self.minimum_altitude = minimum_altitude

    def execute(self, tracker):
        with tracker.lock:
            low_altitude = [
                (callsign, aircraft)
                for callsign, aircraft in tracker.aircrafts.items()
                if self._is_low(aircraft)
            ]

            for callsign, aircraft in low_altitude:
                reason = (
                    "landed" if getattr(aircraft, "on_ground", False)
                    else "low_altitude"
                )
                tracker.remove_aircraft(callsign, reason=reason)

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
