"""
HTTP API for the dashboard.

No module-level tracker: build_services() creates the tracker, the
polling service and the observers when the app starts, and endpoints
receive them through FastAPI's dependency injection (Depends). Tests
pass their own AppServices to create_app().
"""

from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Literal

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from aircraft_tracker import AircraftTracker
from logging_service import LoggingService
from polling_service import (
    MAX_REPLAY_SPEED,
    MIN_REPLAY_SPEED,
    PollingService,
    RecordingNotFoundError,
    SourceBusyError,
)
from ranking_strategies import RANKING_STRATEGIES
from tracker_observers import TrackerObservers, attach_default_observers
from trajectory_predictor import DEFAULT_PREDICTOR


@dataclass
class AppServices:
    """Everything the endpoints need, created once per running app."""

    tracker: AircraftTracker
    # Owns the polling thread and the current data source (live or replay).
    polling: PollingService
    # Statistics, prediction accuracy, geofences and closest-approach
    # alerts, fed by tracker events rather than by polling the tracker.
    observers: TrackerObservers


def build_services():
    tracker = AircraftTracker()
    return AppServices(
        tracker=tracker,
        polling=PollingService(tracker),
        observers=attach_default_observers(tracker),
    )


def get_services(request: Request) -> AppServices:
    return request.app.state.services


Services = Depends(get_services)

router = APIRouter()


def create_app(services=None):
    """
    Build the FastAPI app. Without `services`, they are built at startup
    and polling runs for the app's lifetime. With `services` (tests),
    they are used as given and nothing is started.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if services is not None:
            yield
            return

        LoggingService.initialize()
        app.state.services = build_services()
        app.state.services.polling.start()

        try:
            yield
        finally:
            app.state.services.polling.stop()
            LoggingService.reset()

    app = FastAPI(title="JacobSky API", lifespan=lifespan)
    app.state.services = services
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


@router.get("/")
def root():
    return {"message": "JacobSky API is running"}


TRAJECTORY_STEP_SECONDS = 5


def _round_or_none(value, digits=2):
    return None if value is None else round(value, digits)


def serialize_aircraft(plane, predictor=DEFAULT_PREDICTOR):
    straight_approach = predictor.nearest_approach(plane, "straight")
    curved_approach = predictor.nearest_approach(plane, "curved")

    if straight_approach is None:
        straight_distance, straight_time = None, None
    else:
        straight_distance, straight_time = straight_approach

    if curved_approach is None:
        curved_distance, curved_time = None, None
    else:
        curved_distance, curved_time = curved_approach

    return {
        "id": plane.callsign,
        "callsign": plane.callsign,
        # "observed", or "missing" while waiting out the grace period.
        "state": plane.lifecycle.name,
        "latitude": plane.latitude,
        "longitude": plane.longitude,
        "altitude": plane.altitude,
        "speed": plane.velocity,
        "heading": plane.heading,
        "distance": _round_or_none(plane.distance_from_user),
        "nearest_distance": _round_or_none(straight_distance),
        "nearest_distance_time": straight_time,
        "curved_nearest_distance": _round_or_none(curved_distance),
        "curved_nearest_distance_time": curved_time,
        # Position time (Unix seconds). Trajectory points start at this
        # position and are TRAJECTORY_STEP_SECONDS apart, which lets the
        # frontend animate each aircraft along its predicted path.
        "timestamp": plane.timestamp,
        "trajectory_step_seconds": TRAJECTORY_STEP_SECONDS,
        "straight_trajectory": predictor.trajectory(
            plane, "straight", sample_interval_seconds=TRAJECTORY_STEP_SECONDS
        ),
        "curved_trajectory": predictor.trajectory(
            plane, "curved", sample_interval_seconds=TRAJECTORY_STEP_SECONDS
        ),
    }


@router.get("/aircraft")
def get_aircraft(
    rank: Literal["nearest", "fastest", "predicted"] | None = None,
    services: AppServices = Services,
):
    """
    Return tracked aircraft ranked by `rank` (a RANKING_STRATEGIES key).
    Without `rank`, the tracker's default strategy is used.
    """
    strategy = RANKING_STRATEGIES[rank] if rank is not None else None
    tracker = services.tracker

    # Hold the tracker lock so the worker thread cannot change an
    # aircraft's history while it is being read.
    with tracker.lock:
        return [
            serialize_aircraft(plane)
            for plane in tracker.get_sorted_aircrafts(strategy).values()
        ]


# --- data source: live or replay -------------------------------------------

class ReplayRequest(BaseModel):
    recording: str
    speed: float = Field(default=1.0, ge=MIN_REPLAY_SPEED, le=MAX_REPLAY_SPEED)
    loop: bool = False


class SpeedRequest(BaseModel):
    speed: float = Field(ge=MIN_REPLAY_SPEED, le=MAX_REPLAY_SPEED)


@router.get("/source")
def get_source(services: AppServices = Services):
    """
    Current data source. `clock.now` is the time the aircraft timestamps
    are on (ahead of the wall clock in a sped-up replay) and
    `clock.speed` how fast it runs, so the map can animate to match.
    """
    return services.polling.status()


@router.get("/recordings")
def get_recordings(services: AppServices = Services):
    return services.polling.list_recordings()


@router.post("/source/replay")
def start_replay(request: ReplayRequest, services: AppServices = Services):
    return _switch(
        services.polling.start_replay,
        request.recording,
        speed=request.speed,
        loop=request.loop,
    )


@router.post("/source/replay/speed")
def set_replay_speed(request: SpeedRequest, services: AppServices = Services):
    return _switch(services.polling.set_speed, request.speed)


@router.post("/source/live")
def go_live(services: AppServices = Services):
    return _switch(services.polling.go_live)


def _switch(action, *args, **kwargs):
    try:
        return action(*args, **kwargs)
    except RecordingNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except SourceBusyError as error:
        raise HTTPException(status_code=503, detail=str(error))
    except ValueError as error:
        # Bad speed, speed change while live, or an unreadable recording.
        raise HTTPException(status_code=400, detail=str(error))


# --- observers: statistics, accuracy and alerts ------------------------------

@router.get("/stats")
def get_stats(services: AppServices = Services):
    """Tracker statistics, command queue health and the data source."""
    source = services.polling.status()

    return {
        "tracker": services.observers.statistics.summary(),
        "queue": services.polling.worker_status(),
        "source": {
            "mode": source["mode"],
            "recording": source["recording"],
            "speed": source["speed"],
            "progress": source["progress"],
        },
        "prediction_accuracy": services.observers.accuracy.summary(),
    }


@router.get("/events")
def get_events(
    limit: int = Query(default=50, ge=1, le=200),
    services: AppServices = Services,
):
    """Recent geofence and closest-approach events, newest first."""
    return services.observers.events.recent(limit)


@router.get("/geofences")
def get_geofences(services: AppServices = Services):
    return [fence.summary() for fence in services.observers.geofences]


# The app uvicorn serves: `uvicorn api:app`.
app = create_app()
