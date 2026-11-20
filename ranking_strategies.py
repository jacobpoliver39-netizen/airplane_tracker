from abc import ABC, abstractmethod

from trajectory_predictor import DEFAULT_PREDICTOR


class RankingStrategy(ABC):
    """Interface for ranking aircraft."""

    @abstractmethod
    def sort_aircrafts(self, aircrafts):
        """Return aircraft sorted according to this strategy."""
        pass


class NearestStrategy(RankingStrategy):
    """Rank aircraft from nearest to farthest."""

    def sort_aircrafts(self, aircrafts):
        return dict(sorted(
            aircrafts.items(),
            key=lambda item: item[1].get_distance_from_user(),
        ))


class FastestApproachStrategy(RankingStrategy):
    """Rank aircraft by highest approach speed first."""

    def sort_aircrafts(self, aircrafts):
        def approach_speed(aircraft):
            speed = aircraft.get_approach_speed_towards_user()

            # Aircraft without sufficient history rank last.
            return float("-inf") if speed is None else speed

        return dict(sorted(
            aircrafts.items(),
            key=lambda item: approach_speed(item[1]),
            reverse=True,
        ))


class NearestPredictedApproachStrategy(RankingStrategy):
    """
    Rank aircraft by how close they are predicted to come to the user,
    closest first.

    Uses the curved (CTRV) nearest approach when it is available, and
    otherwise the straight-line one, which for an aircraft moving away
    is its current distance. Ties are broken by current distance.
    """

    def __init__(self, predictor=DEFAULT_PREDICTOR):
        self._predictor = predictor

    def predicted_approach_distance(self, aircraft):
        for strategy in ("curved", "straight"):
            approach = self._predictor.nearest_approach(aircraft, strategy)

            if approach is not None:
                return approach.distance_miles

        return aircraft.get_distance_from_user()

    def sort_aircrafts(self, aircrafts):
        return dict(sorted(
            aircrafts.items(),
            key=lambda item: (
                self.predicted_approach_distance(item[1]),
                item[1].get_distance_from_user(),
            ),
        ))


# Strategies selectable by name, e.g. GET /aircraft?rank=fastest.
RANKING_STRATEGIES = {
    "nearest": NearestStrategy(),
    "fastest": FastestApproachStrategy(),
    "predicted": NearestPredictedApproachStrategy(),
}
