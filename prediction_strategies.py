"""
Strategies for predicting where an aircraft will go.

Each strategy answers "how should this aircraft's movement be
predicted?" in two steps:

1. initial_state(aircraft) captures what the prediction starts from
   (a MotionState), or None when the strategy cannot predict yet
   (e.g. not enough history to estimate a turn).
2. predict_offset(state, seconds) gives the east/north offset in miles
   after that many seconds.

Capturing the state separately is what lets TrajectoryPredictor save a
prediction now and score it against the position reported later.

Positions in the history are (timestamp, longitude, latitude); units
follow the rest of the tracker (mph, degrees, deg/s, statute miles).
"""

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import NamedTuple

from calculator import Calculator

# How many recent positions the history-based estimates use.
HISTORY_WINDOW = 6


@dataclass(frozen=True)
class MotionState:
    """Where a prediction starts: position, speed, track and turn rate."""

    timestamp: float
    longitude: float
    latitude: float
    speed_mph: float
    heading: float  # degrees, the track the prediction starts on
    turn_rate: float  # deg/s, positive = clockwise; 0 = straight line


class NearestApproach(NamedTuple):
    distance_miles: float
    time_seconds: float | None  # None when there is no future closest point


def recent_positions(aircraft, count=HISTORY_WINDOW):
    """The aircraft's last `count` positions as (timestamp, lon, lat)."""
    positions = sorted(aircraft.location_history.items())[-count:]

    return [
        (timestamp, position.get_longitude(), position.get_latitude())
        for timestamp, position in positions
    ]


class PredictionStrategy(ABC):
    """Interface for a model of aircraft movement."""

    # Short identifier used in API fields and prediction-error keys.
    name: str

    @abstractmethod
    def initial_state(self, aircraft) -> MotionState | None:
        """Capture the state a prediction starts from, or None."""

    def predict_offset(self, state: MotionState, elapsed_seconds):
        """
        (east_miles, north_miles) from the start position after
        elapsed_seconds. The default moves at constant speed and turn
        rate (CTRV), which with a zero turn rate is a straight line.
        """
        return Calculator.predict_ctrv_position(
            state.speed_mph, state.heading, state.turn_rate, elapsed_seconds
        )

    def nearest_approach(
        self,
        state: MotionState,
        user_longitude,
        user_latitude,
        prediction_seconds=60,
        sample_interval_seconds=2,
    ):
        """
        Closest predicted distance to the user, found by sampling the
        path. Returns None when the closest sample is at either end of
        the window: now (moving away) or the end (still closing).
        """
        if prediction_seconds < 0 or sample_interval_seconds <= 0:
            return None

        start_east, start_north = Calculator.gps_to_local_coordinates(
            state.longitude, state.latitude, user_longitude, user_latitude
        )
        sample_times = range(0, prediction_seconds + 1, sample_interval_seconds)
        closest = None

        for elapsed in sample_times:
            offset = self.predict_offset(state, elapsed)

            if offset is None:
                return None

            # The user is the origin of the local east/north frame.
            distance = math.hypot(start_east + offset[0], start_north + offset[1])

            if closest is None or distance < closest[0]:
                closest = (distance, elapsed)

        if closest is None or closest[1] in (sample_times[0], sample_times[-1]):
            return None

        return NearestApproach(*closest)


class StraightLinePredictionStrategy(PredictionStrategy):
    """Continue at the reported speed along the reported heading."""

    name = "straight"

    def initial_state(self, aircraft):
        return MotionState(
            timestamp=aircraft.timestamp,
            longitude=aircraft.longitude,
            latitude=aircraft.latitude,
            speed_mph=aircraft.velocity,
            heading=aircraft.heading,
            turn_rate=0.0,
        )

    def nearest_approach(self, state, user_longitude, user_latitude, **_):
        """
        Exact closest point of a straight line, with no time window.
        Moving away, the closest distance is the current one and the time
        is None.
        """
        bearing = Calculator.bearing_angle_from_user_to_plane(
            state.longitude, state.latitude, user_longitude, user_latitude
        )
        distance = Calculator.calculate_haversine_distance(
            user_longitude, user_latitude, state.longitude, state.latitude
        )

        return NearestApproach(
            Calculator.nearest_approach(bearing, distance, state.heading),
            Calculator.nearest_approach_time(
                bearing, distance, state.heading, state.speed_mph
            ),
        )


class CTRVPredictionStrategy(PredictionStrategy):
    """
    Constant Turn Rate and Velocity: start from the reported speed and
    heading, and keep turning at the rate estimated from recent history.

    The history only supplies the turn rate. Starting from a track fitted
    to past positions lags behind a turning aircraft (up to ~100 degrees),
    which drew the curve out of the side of the plane.

    Rule: if OpenSky reported the same heading in the aircraft's two most
    recent positions, it is flying straight, so there is no curved
    prediction and everything falls back to the straight line. (The
    turn-rate estimate looks back further and would still bend the path
    after a turn has ended.)
    """

    name = "curved"

    # Headings at most this far apart count as "the same". 0 = identical
    # (0 and 360 are treated as the same heading).
    same_heading_tolerance_degrees = 0.5

    def estimate_turn_rate(self, aircraft):
        return Calculator.estimate_turn_rate(recent_positions(aircraft))

    def heading_unchanged(self, aircraft):
        """True if the two most recent reported headings are the same."""
        latest = sorted(aircraft.location_history.items())[-2:]

        if len(latest) < 2:
            return False

        (_, previous), (_, current) = latest

        if previous.get_heading() is None or current.get_heading() is None:
            return False

        change = Calculator.angular_difference(
            current.get_heading(), previous.get_heading()
        )
        return abs(change) <= self.same_heading_tolerance_degrees

    def initial_state(self, aircraft):
        if self.heading_unchanged(aircraft):
            return None

        turn_rate = self.estimate_turn_rate(aircraft)

        if turn_rate is None:
            return None

        return MotionState(
            timestamp=aircraft.timestamp,
            longitude=aircraft.longitude,
            latitude=aircraft.latitude,
            speed_mph=aircraft.velocity,
            heading=aircraft.heading,
            turn_rate=turn_rate,
        )


class HistoricalPredictionStrategy(PredictionStrategy):
    """
    Straight line at the speed and track fitted (least squares) to recent
    positions, ignoring the reported speed and heading.

    Used to compare prediction accuracy, not drawn on the map: during a
    turn the fitted track lags the real one.
    """

    name = "historical"

    def initial_state(self, aircraft):
        motion = Calculator.estimate_ground_motion(recent_positions(aircraft))

        if motion is None:
            return None

        speed_mph, track = motion

        return MotionState(
            timestamp=aircraft.timestamp,
            longitude=aircraft.longitude,
            latitude=aircraft.latitude,
            speed_mph=speed_mph,
            heading=track,
            turn_rate=0.0,
        )
