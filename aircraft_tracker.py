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

    Also the Subject of the Observer pattern: subscribed TrackerObserver
    objects (tracker_observers.py) are told when aircraft are added,
    updated or removed and when the tracker is cleared. Observers run
    synchronously on the thread that made the change (the tracker
    worker), holding the lock, so they must be quick. An observer that
    raises is logged and skipped; it cannot break an update.
    """

    def __init__(self, ranking_strategy=None):
        self.aircrafts = {}
        self.lock = threading.RLock()
        self._observers = []
        self.set_ranking_strategy(
            ranking_strategy if ranking_strategy is not None
            else NearestStrategy()
        )

    def set_ranking_strategy(self, ranking_strategy: RankingStrategy):
        if not isinstance(ranking_strategy, RankingStrategy):
            raise TypeError("ranking_strategy must implement RankingStrategy")

        self._ranking_strategy = ranking_strategy

    # --- observers -------------------------------------------------------

    def subscribe(self, observer):
        with self.lock:
            if observer not in self._observers:
                self._observers.append(observer)

    def unsubscribe(self, observer):
        with self.lock:
            if observer in self._observers:
                self._observers.remove(observer)

    @property
    def observers(self):
        with self.lock:
            return list(self._observers)

    def _notify(self, event, *args):
        for observer in self.observers:
            try:
                getattr(observer, event)(*args)
            except Exception:
                logger.exception(
                    "Observer %s failed on %s", type(observer).__name__, event
                )

    # --- changes ---------------------------------------------------------

    def add_aircraft(self, aircraft):
        callsign = aircraft.callsign

        with self.lock:
            self.aircrafts[callsign] = aircraft
            self._notify("on_aircraft_added", aircraft)

        logger.info("Aircraft added to tracker: %s", callsign)

    def notify_aircraft_updated(self, aircraft, prediction_result=None):
        """
        Announce that a tracked aircraft took a new position.
        prediction_result is TrajectoryPredictor.evaluate's score of the
        previous prediction against this position, if there was one.
        """
        with self.lock:
            self._notify("on_aircraft_updated", aircraft, prediction_result)

    def remove_aircraft(self, callsign, reason="removed"):
        """reason: e.g. 'missing', 'landed', 'low_altitude'."""
        with self.lock:
            aircraft = self.aircrafts.pop(callsign)
            self._notify("on_aircraft_removed", aircraft, reason)

        logger.info("Aircraft removed from tracker: %s (%s)", callsign, reason)

    def clear(self):
        """Stop tracking every aircraft (e.g. when the data source changes)."""
        with self.lock:
            count = len(self.aircrafts)
            self.aircrafts.clear()
            self._notify("on_tracker_cleared")

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
