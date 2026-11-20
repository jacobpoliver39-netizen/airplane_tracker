"""
Observers of the AircraftTracker (the Observer pattern).

The tracker only announces what happened (added, updated, removed,
cleared); each observer decides what to do with it. New behaviour, such
as statistics, alerts or accuracy tracking, is added by subscribing
another observer, without changing the tracker or the commands.

Observer methods run on the tracker worker thread while the tracker
lock is held, so they only record what they need. Each observer has
its own lock because the API reads its summary from another thread.
"""

import logging
import statistics
import threading
import time
from collections import deque
from dataclasses import dataclass, field

import config
from calculator import Calculator
from prediction_strategies import CTRVPredictionStrategy

logger = logging.getLogger(__name__)


class TrackerObserver:
    """
    Base class for tracker observers. Every event has a no-op default,
    so an observer only overrides the events it cares about.
    """

    def on_aircraft_added(self, aircraft):
        pass

    def on_aircraft_updated(self, aircraft, prediction_result):
        """prediction_result: TrajectoryPredictor.evaluate's score, or None."""

    def on_aircraft_removed(self, aircraft, reason):
        pass

    def on_tracker_cleared(self):
        """The data source changed; forget per-session state."""


# --- event log -------------------------------------------------------------

class EventLog:
    """
    Recent notable events (geofence entries/exits, closest approaches),
    newest last. Shared by the observers that raise alerts.
    """

    def __init__(self, max_events=200):
        self._events = deque(maxlen=max_events)
        self._lock = threading.Lock()
        self._next_id = 1

    def add(self, event_type, aircraft, **details):
        event = {
            "type": event_type,
            "callsign": aircraft.callsign,
            # Position time, so replayed events carry replay time.
            "time": aircraft.timestamp,
            "latitude": aircraft.latitude,
            "longitude": aircraft.longitude,
            "altitude": aircraft.altitude,
            **details,
        }

        with self._lock:
            event["id"] = self._next_id
            self._next_id += 1
            self._events.append(event)

        logger.info("Event %s: %s %s", event_type, aircraft.callsign, details)
        return event

    def recent(self, limit=50):
        """Newest first."""
        with self._lock:
            return list(reversed(self._events))[:limit]

    def clear(self):
        with self._lock:
            self._events.clear()


# --- statistics ------------------------------------------------------------

class StatisticsObserver(TrackerObserver):
    """Counts aircraft and updates, and measures the update rate."""

    def __init__(self, clock=time.monotonic, rate_window_seconds=60):
        self._clock = clock
        self._rate_window = rate_window_seconds
        self._lock = threading.Lock()
        self._started = clock()
        self._reset()

    def _reset(self):
        self._added = 0
        self._updated = 0
        self._removed_by_reason = {}
        self._tracked = 0
        self._peak_tracked = 0
        self._callsigns_seen = set()
        self._update_times = deque()

    def on_aircraft_added(self, aircraft):
        with self._lock:
            self._added += 1
            self._tracked += 1
            self._peak_tracked = max(self._peak_tracked, self._tracked)
            self._callsigns_seen.add(aircraft.callsign)

    def on_aircraft_updated(self, aircraft, prediction_result):
        with self._lock:
            self._updated += 1
            self._update_times.append(self._clock())
            self._trim()

    def on_aircraft_removed(self, aircraft, reason):
        with self._lock:
            self._removed_by_reason[reason] = (
                self._removed_by_reason.get(reason, 0) + 1
            )
            self._tracked = max(0, self._tracked - 1)

    def on_tracker_cleared(self):
        with self._lock:
            self._reset()
            self._started = self._clock()

    def _trim(self):
        cutoff = self._clock() - self._rate_window
        while self._update_times and self._update_times[0] < cutoff:
            self._update_times.popleft()

    def summary(self):
        with self._lock:
            self._trim()
            return {
                "tracked": self._tracked,
                "peak_tracked": self._peak_tracked,
                "distinct_aircraft": len(self._callsigns_seen),
                "added": self._added,
                "updated": self._updated,
                "removed": dict(self._removed_by_reason),
                "updates_last_minute": len(self._update_times),
                "uptime_seconds": round(self._clock() - self._started, 1),
            }


# --- prediction accuracy ---------------------------------------------------

class PredictionAccuracyObserver(TrackerObserver):
    """
    Collects each prediction strategy's error from every update and
    summarises it overall and separately for turning and straight flight
    (by the turn rate estimated from the aircraft's history).
    """

    SEGMENTS = ("all", "turning", "straight")

    def __init__(
        self,
        max_samples=5000,
        turning_threshold=1.0,  # deg/s
        turn_rate_estimator=None,
    ):
        self._max_samples = max_samples
        self._turning_threshold = turning_threshold
        self._estimate_turn_rate = (
            turn_rate_estimator or CTRVPredictionStrategy().estimate_turn_rate
        )
        self._lock = threading.Lock()
        self._samples = {}  # (segment, strategy) -> deque of errors
        self._scored_updates = 0

    def on_aircraft_updated(self, aircraft, prediction_result):
        if prediction_result is None:
            return

        segments = ["all"]
        turn_rate = self._estimate_turn_rate(aircraft)

        if turn_rate is not None:
            segments.append(
                "turning" if abs(turn_rate) >= self._turning_threshold
                else "straight"
            )

        with self._lock:
            self._scored_updates += 1

            for key, error in prediction_result.items():
                if not key.endswith("_error_miles") or error is None:
                    continue

                strategy = key.removesuffix("_error_miles")

                for segment in segments:
                    self._samples.setdefault(
                        (segment, strategy), deque(maxlen=self._max_samples)
                    ).append(error)

    def on_tracker_cleared(self):
        with self._lock:
            self._samples.clear()
            self._scored_updates = 0

    def summary(self):
        """
        {"scored_updates", "segments": {segment: {strategy: {count,
        mean_miles, median_miles}}}} over the most recent max_samples.
        """
        with self._lock:
            segments = {segment: {} for segment in self.SEGMENTS}

            for (segment, strategy), errors in sorted(self._samples.items()):
                segments[segment][strategy] = {
                    "count": len(errors),
                    "mean_miles": round(statistics.fmean(errors), 4),
                    "median_miles": round(statistics.median(errors), 4),
                }

            return {
                "scored_updates": self._scored_updates,
                "turning_threshold_deg_per_s": self._turning_threshold,
                "segments": segments,
            }


# --- alerts ----------------------------------------------------------------

class GeofenceObserver(TrackerObserver):
    """
    A circular geofence: records an event when an aircraft enters or
    leaves the circle (including leaving by being removed).
    """

    def __init__(self, name, longitude, latitude, radius_miles, event_log):
        self.name = name
        self.longitude = longitude
        self.latitude = latitude
        self.radius_miles = radius_miles
        self._event_log = event_log
        self._lock = threading.Lock()
        self._inside = {}  # callsign -> distance when last checked

    def distance_to(self, aircraft):
        return Calculator.calculate_haversine_distance(
            self.longitude, self.latitude, aircraft.longitude, aircraft.latitude
        )

    def on_aircraft_added(self, aircraft):
        self._check(aircraft)

    def on_aircraft_updated(self, aircraft, prediction_result):
        self._check(aircraft)

    def on_aircraft_removed(self, aircraft, reason):
        with self._lock:
            was_inside = self._inside.pop(aircraft.callsign, None) is not None

        if was_inside:
            self._event(
                "geofence_exit", aircraft, self.distance_to(aircraft), reason=reason
            )

    def on_tracker_cleared(self):
        with self._lock:
            self._inside.clear()

    def _check(self, aircraft):
        distance = self.distance_to(aircraft)
        inside = distance <= self.radius_miles

        with self._lock:
            was_inside = aircraft.callsign in self._inside

            if inside:
                self._inside[aircraft.callsign] = distance
            else:
                self._inside.pop(aircraft.callsign, None)

        if inside and not was_inside:
            self._event("geofence_enter", aircraft, distance)
        elif was_inside and not inside:
            self._event("geofence_exit", aircraft, distance)

    def _event(self, event_type, aircraft, distance, **details):
        self._event_log.add(
            event_type,
            aircraft,
            geofence=self.name,
            distance_miles=round(distance, 2),
            **details,
        )

    def summary(self):
        with self._lock:
            inside = sorted(self._inside)

        return {
            "name": self.name,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "radius_miles": self.radius_miles,
            "aircraft_inside": inside,
        }


@dataclass
class _ApproachTrack:
    distance: float
    timestamp: float
    closing: bool = False


class ClosestApproachObserver(TrackerObserver):
    """
    Detects when an aircraft passes its closest point to the user: its
    distance was falling and has started to rise. Records the closest
    observed distance, if it is within report_within_miles.
    """

    def __init__(self, event_log, report_within_miles=10.0):
        self._event_log = event_log
        self._report_within = report_within_miles
        self._lock = threading.Lock()
        self._tracks = {}

    def on_aircraft_added(self, aircraft):
        with self._lock:
            self._tracks[aircraft.callsign] = _ApproachTrack(
                aircraft.distance_from_user, aircraft.timestamp
            )

    def on_aircraft_updated(self, aircraft, prediction_result):
        distance = aircraft.distance_from_user
        passed = None

        with self._lock:
            track = self._tracks.get(aircraft.callsign)

            if track is None:
                self._tracks[aircraft.callsign] = _ApproachTrack(
                    distance, aircraft.timestamp
                )
                return

            if distance < track.distance:
                track.closing = True
            elif distance > track.distance and track.closing:
                passed = (track.distance, track.timestamp)
                track.closing = False

            track.distance = distance
            track.timestamp = aircraft.timestamp

        if passed is not None and passed[0] <= self._report_within:
            self._event_log.add(
                "closest_approach",
                aircraft,
                distance_miles=round(passed[0], 2),
                closest_time=passed[1],
            )

    def on_aircraft_removed(self, aircraft, reason):
        with self._lock:
            self._tracks.pop(aircraft.callsign, None)

    def on_tracker_cleared(self):
        with self._lock:
            self._tracks.clear()


# --- wiring ----------------------------------------------------------------

@dataclass
class TrackerObservers:
    """The observers the application runs with, for the API to read."""

    events: EventLog
    statistics: StatisticsObserver
    accuracy: PredictionAccuracyObserver
    closest_approach: ClosestApproachObserver
    geofences: list[GeofenceObserver] = field(default_factory=list)

    def all(self):
        return [
            self.statistics,
            self.accuracy,
            self.closest_approach,
            *self.geofences,
        ]


class _EventLogReset(TrackerObserver):
    """Empties the event log when the data source changes."""

    def __init__(self, event_log):
        self._event_log = event_log

    def on_tracker_cleared(self):
        self._event_log.clear()


def attach_default_observers(tracker, geofences=None):
    """Create the standard observers and subscribe them to `tracker`."""
    events = EventLog()
    fences = geofences if geofences is not None else config.GEOFENCES

    observers = TrackerObservers(
        events=events,
        statistics=StatisticsObserver(),
        accuracy=PredictionAccuracyObserver(),
        closest_approach=ClosestApproachObserver(
            events, report_within_miles=config.CLOSEST_APPROACH_REPORT_MILES
        ),
        geofences=[
            GeofenceObserver(
                fence["name"],
                fence["longitude"],
                fence["latitude"],
                fence["radius_miles"],
                events,
            )
            for fence in fences
        ],
    )

    for observer in [*observers.all(), _EventLogReset(events)]:
        tracker.subscribe(observer)

    return observers
