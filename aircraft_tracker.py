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

    def clear(self):
        """Stop tracking every aircraft (e.g. when the data source changes)."""
        with self.lock:
            count = len(self.aircrafts)
            self.aircrafts.clear()

        logger.info("Tracker cleared (%d aircraft removed)", count)

    def get_sorted_aircrafts(self, ranking_strategy=None):
        """
        Return aircraft ranked by the given strategy, or by the tracker's
        default strategy when none is given. Passing a strategy per call
        (as the API does) avoids changing the shared default.
        """
        strategy = (
            ranking_strategy if ranking_strategy is not None
            else self._ranking_strategy
        )

        if not isinstance(strategy, RankingStrategy):
            raise TypeError("ranking_strategy must implement RankingStrategy")

        with self.lock:
            return strategy.sort_aircrafts(dict(self.aircrafts))
