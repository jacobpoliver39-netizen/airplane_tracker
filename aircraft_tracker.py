# Class to track aircraft in relation to a given position.

from ranking_strategies import NearestStrategy, RankingStrategy


class AircraftTracker:

    def __init__(self, ranking_strategy=None):
        self.aircrafts = {}
        self.set_ranking_strategy(
            ranking_strategy if ranking_strategy is not None
            else NearestStrategy()
        )

    def set_ranking_strategy(self, ranking_strategy: RankingStrategy):
        if not isinstance(ranking_strategy, RankingStrategy):
            raise TypeError("ranking_strategy must implement RankingStrategy")

        self._ranking_strategy = ranking_strategy

    def add_aircraft(self, aircraft):
        callsign = aircraft.callsign
        self.aircrafts[callsign] = aircraft
        print("Aircraft Added to List")

    def display_all_callsigns(self):
        for callsign in self.aircrafts:
            print(callsign)

    def display_aircraft_info_nearest_to_farthest(self):
        sorted_dict = self.sort_aircrafts_by_distance()
        for aircraft in sorted_dict.values():
            print(aircraft.get_info())

    def get_sorted_aircrafts(self):
        """Return aircraft ranked using the currently selected strategy."""
        return self._ranking_strategy.sort_aircrafts(self.aircrafts)

    def sort_aircrafts_by_distance(self):
        """Return aircraft sorted from nearest to farthest."""
        return NearestStrategy().sort_aircrafts(self.aircrafts)
