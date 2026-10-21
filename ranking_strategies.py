from abc import ABC, abstractmethod


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
            if not isinstance(speed, (int, float)):
                return float("-inf")

            return speed

        return dict(sorted(
            aircrafts.items(),
            key=lambda item: approach_speed(item[1]),
            reverse=True,
        ))
