# Class to track aircraft in relation to a given position.

import logging
import threading

from ranking_strategies import NearestStrategy, RankingStrategy

logger = logging.getLogger(__name__)


class AircraftTracker:
    """
    Registry of tracked aircraft, shared by the polling thread and the API.

    Hold `lock` while reading or changing the tracked aircraft (including
    the Aircraft objects themselves) from more than one step. It is
    re-entrant, so the methods below can be called while holding it.
    """

    def __init__(self, ranking_strategy=None):
        self.aircrafts = {}
        self.lock = threading.RLock()
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

        with self.lock:
            self.aircrafts[callsign] = aircraft

        logger.info("Aircraft added to tracker: %s", callsign)

    def remove_aircraft(self, callsign):
        with self.lock:
            del self.aircrafts[callsign]

        logger.info("Aircraft removed from tracker: %s", callsign)

    def get_sorted_aircrafts(self):
        """Return aircraft ranked using the currently selected strategy."""
        with self.lock:
            return self._ranking_strategy.sort_aircrafts(dict(self.aircrafts))
