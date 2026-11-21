"""
The prediction engine: everything about where an aircraft is going.

TrajectoryPredictor holds a set of PredictionStrategy objects and uses
them to produce trajectories and nearest approaches, classify the
approach, and snapshot predictions so they can be scored once the next
position arrives. Aircraft only stores state and history; it knows
nothing about predictions.

The predictor is stateless (strategies hold no per-aircraft data), so
one instance can be shared by the API, the ranking strategies and the
update commands.
"""

import logging
from dataclasses import dataclass

from calculator import Calculator
from prediction_strategies import (
    CTRVPredictionStrategy,
    HistoricalPredictionStrategy,
    MotionState,
    PredictionStrategy,
    StraightLinePredictionStrategy,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PredictionSnapshot:
    """Each strategy's starting state at one moment (None = no prediction)."""

    timestamp: float
    states: dict[str, MotionState | None]


class TrajectoryPredictor:

    def __init__(self, strategies=None):
        if strategies is None:
            strategies = [
                StraightLinePredictionStrategy(),
                CTRVPredictionStrategy(),
                HistoricalPredictionStrategy(),
            ]

        self._strategies = {}

        for strategy in strategies:
            if not isinstance(strategy, PredictionStrategy):
                raise TypeError("strategies must implement PredictionStrategy")
            if strategy.name in self._strategies:
                raise ValueError(f"Duplicate strategy name {strategy.name!r}")
            self._strategies[strategy.name] = strategy

    @property
    def strategy_names(self):
        return list(self._strategies)

    def strategy(self, strategy):
        """Look up a strategy by name; a strategy object is returned as is."""
        if isinstance(strategy, PredictionStrategy):
            return strategy

        try:
            return self._strategies[strategy]
        except KeyError:
            raise KeyError(f"Unknown prediction strategy {strategy!r}") from None

    # --- predictions for display -----------------------------------------

    def trajectory(
        self,
        aircraft,
        strategy,
        prediction_seconds=60,
        sample_interval_seconds=5,
    ):
        """
        Future [latitude, longitude] points, one every
        sample_interval_seconds from the current position, or None if the
        strategy cannot predict this aircraft yet.
        """
        if prediction_seconds < 0 or sample_interval_seconds <= 0:
            return None

        strategy = self.strategy(strategy)
        state = strategy.initial_state(aircraft)

        if state is None:
            return None

        trajectory = []

        for elapsed in range(0, prediction_seconds + 1, sample_interval_seconds):
            position = self._position_after(strategy, state, elapsed)

            if position is None:
                return None

            longitude, latitude = position
            trajectory.append([latitude, longitude])

        return trajectory

    def nearest_approach(self, aircraft, strategy):
        """
        NearestApproach(distance_miles, time_seconds) to the user, or None
        when the strategy cannot predict or finds no closest point inside
        its window (see PredictionStrategy.nearest_approach).
        """
        strategy = self.strategy(strategy)
        state = strategy.initial_state(aircraft)

        if state is None:
            return None

        return strategy.nearest_approach(
            state, aircraft.user_longitude, aircraft.user_latitude
        )

    # --- prediction accuracy ---------------------------------------------

    def snapshot(self, aircraft):
        """Capture every strategy's prediction from the aircraft's current state."""
        return PredictionSnapshot(
            timestamp=aircraft.timestamp,
            states={
                name: strategy.initial_state(aircraft)
                for name, strategy in self._strategies.items()
            },
        )

    def evaluate(self, snapshot, actual_timestamp, actual_longitude, actual_latitude):
        """
        Distance in miles between each strategy's prediction and where the
        aircraft actually was at actual_timestamp.

        Returns {"timestamp", "elapsed_seconds", "<name>_error_miles", ...}
        with None for strategies that had no prediction, or None when the
        actual position is not later than the snapshot.
        """
        elapsed = actual_timestamp - snapshot.timestamp

        if elapsed <= 0:
            return None

        result = {"timestamp": snapshot.timestamp, "elapsed_seconds": elapsed}

        for name, state in snapshot.states.items():
            error = None

            if state is not None:
                position = self._position_after(self._strategies[name], state, elapsed)

                if position is not None:
                    error = Calculator.calculate_haversine_distance(
                        position[0], position[1], actual_longitude, actual_latitude
                    )

            result[f"{name}_error_miles"] = error

        return result

    @staticmethod
    def _position_after(strategy, state, elapsed_seconds):
        """(longitude, latitude) predicted elapsed_seconds after state."""
        offset = strategy.predict_offset(state, elapsed_seconds)

        if offset is None:
            return None

        return Calculator.local_coordinates_to_gps(
            offset[0], offset[1], state.longitude, state.latitude
        )


# Shared, stateless default used by the API, ranking and update commands.
DEFAULT_PREDICTOR = TrajectoryPredictor()
