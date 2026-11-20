"""
Lifecycle of a tracked aircraft (the State pattern).

    Observed ──missed a poll──▶ Missing ──grace period over──▶ Removed
       ▲                          │                               ▲
       └──────reported again──────┘                               │
       └──────────────landed / low / source changed───────────────┘

Each state decides which transitions it allows and how it behaves:

- ObservedState: in the latest response. Never expires.
- MissingState: tracked but absent from recent responses. Expires once
  its last position is older than the grace period.
- RemovedState: final. Every transition raises AircraftRemovedError, and
  a removed Aircraft refuses updates. If the same callsign appears again
  later, the tracker creates a new Aircraft with a new lifecycle.

AircraftLifecycle is the context: it holds the current state and
delegates each event to it.
"""

import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class AircraftRemovedError(RuntimeError):
    """A removed aircraft was asked to change state or be updated."""


class AircraftState(ABC):
    """One stage of an aircraft's lifecycle."""

    name: str

    @abstractmethod
    def observed(self, lifecycle):
        """The aircraft was in the latest response. Returns the next state."""

    @abstractmethod
    def missed(self, lifecycle, poll_time):
        """The aircraft was absent from the response at poll_time."""

    @abstractmethod
    def removed(self, lifecycle, reason):
        """The tracker dropped the aircraft."""

    @abstractmethod
    def is_expired(self, aircraft, current_time, grace_seconds):
        """Should a missing-aircraft check remove it now?"""

    @property
    def accepts_updates(self):
        return True

    def __repr__(self):
        return f"<{type(self).__name__}>"


class ObservedState(AircraftState):
    name = "observed"

    def observed(self, lifecycle):
        return self

    def missed(self, lifecycle, poll_time):
        return MissingState(since=poll_time)

    def removed(self, lifecycle, reason):
        return RemovedState(reason)

    def is_expired(self, aircraft, current_time, grace_seconds):
        return False


class MissingState(AircraftState):
    name = "missing"

    def __init__(self, since):
        # Time of the first poll the aircraft was absent from.
        self.since = since

    def observed(self, lifecycle):
        return ObservedState()

    def missed(self, lifecycle, poll_time):
        return self  # still missing, since the first missed poll

    def removed(self, lifecycle, reason):
        return RemovedState(reason)

    def is_expired(self, aircraft, current_time, grace_seconds):
        # Without a time or a grace period, missing means gone.
        if current_time is None or grace_seconds <= 0:
            return True

        return current_time - aircraft.timestamp > grace_seconds


class RemovedState(AircraftState):
    """Final state: nothing can bring the aircraft back."""

    name = "removed"

    def __init__(self, reason):
        self.reason = reason

    def _refuse(self, lifecycle, transition):
        raise AircraftRemovedError(
            f"{lifecycle.callsign} was removed ({self.reason}) and cannot "
            f"be {transition}"
        )

    def observed(self, lifecycle):
        self._refuse(lifecycle, "observed again")

    def missed(self, lifecycle, poll_time):
        self._refuse(lifecycle, "marked missing")

    def removed(self, lifecycle, reason):
        self._refuse(lifecycle, "removed again")

    def is_expired(self, aircraft, current_time, grace_seconds):
        return True

    @property
    def accepts_updates(self):
        return False


class AircraftLifecycle:
    """Holds an aircraft's current state and applies transitions to it."""

    def __init__(self, callsign):
        self.callsign = callsign
        self.state = ObservedState()

    @property
    def name(self):
        return self.state.name

    @property
    def is_removed(self):
        return isinstance(self.state, RemovedState)

    def mark_observed(self):
        self._change(self.state.observed(self))

    def mark_missing(self, poll_time=None):
        self._change(self.state.missed(self, poll_time))

    def mark_removed(self, reason="removed"):
        self._change(self.state.removed(self, reason))

    def is_expired(self, aircraft, current_time, grace_seconds):
        return self.state.is_expired(aircraft, current_time, grace_seconds)

    def _change(self, new_state):
        if new_state is not self.state:
            logger.debug(
                "%s: %s -> %s", self.callsign, self.state.name, new_state.name
            )
            self.state = new_state
