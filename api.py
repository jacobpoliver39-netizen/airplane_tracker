
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from logging_service import LoggingService
from polling_service import (
    MAX_REPLAY_SPEED,
    MIN_REPLAY_SPEED,
    PollingService,
    RecordingNotFoundError,
    SourceBusyError,
)
from ranking_strategies import RANKING_STRATEGIES
from tracker_observers import attach_default_observers
from trajectory_predictor import DEFAULT_PREDICTOR
from tracker_state import aircraft_tracker


# Owns the polling thread and the current data source (live or replay).
polling_service = PollingService(aircraft_tracker)

# Statistics, prediction accuracy, geofences and closest-approach alerts,
# all fed by tracker events rather than by polling the tracker.
observers = attach_default_observers(aircraft_tracker)


@asynccontextmanager
async def lifespan(app: FastAPI):
    LoggingService.initialize()
    polling_service.start()

    try:
        yield
    finally:
        polling_service.stop()
        LoggingService.reset()


app = FastAPI(title="JacobSky API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

@app.get("/")
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


@app.get("/aircraft")
def get_aircraft(rank: Literal["nearest", "fastest", "predicted"] | None = None):
    """
    Return tracked aircraft ranked by `rank` (a RANKING_STRATEGIES key).
    Without `rank`, the tracker's default strategy is used.
    """
    strategy = RANKING_STRATEGIES[rank] if rank is not None else None

    # Hold the tracker lock so the polling thread cannot change an
    # aircraft's history while it is being read.
    with aircraft_tracker.lock:
        return [
            serialize_aircraft(plane)
            for plane in aircraft_tracker.get_sorted_aircrafts(strategy).values()
        ]


# --- data source: live or replay -------------------------------------------

class ReplayRequest(BaseModel):
    recording: str
    speed: float = Field(default=1.0, ge=MIN_REPLAY_SPEED, le=MAX_REPLAY_SPEED)
    loop: bool = False


class SpeedRequest(BaseModel):
    speed: float = Field(ge=MIN_REPLAY_SPEED, le=MAX_REPLAY_SPEED)


@app.get("/source")
def get_source():
    """
    Current data source. `clock.now` is the time the aircraft timestamps
    are on (ahead of the wall clock in a sped-up replay) and
    `clock.speed` how fast it runs, so the map can animate to match.
    """
    return polling_service.status()


@app.get("/recordings")
def get_recordings():
    return polling_service.list_recordings()


@app.post("/source/replay")
def start_replay(request: ReplayRequest):
    return _switch(
        polling_service.start_replay,
        request.recording,
        speed=request.speed,
        loop=request.loop,
    )


@app.post("/source/replay/speed")
def set_replay_speed(request: SpeedRequest):
    return _switch(polling_service.set_speed, request.speed)


@app.post("/source/live")
def go_live():
    return _switch(polling_service.go_live)


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

@app.get("/stats")
def get_stats():
    """Tracker statistics, command queue health and the data source."""
    source = polling_service.status()

    return {
        "tracker": observers.statistics.summary(),
        "queue": polling_service.worker_status(),
        "source": {
            "mode": source["mode"],
            "recording": source["recording"],
            "speed": source["speed"],
            "progress": source["progress"],
        },
        "prediction_accuracy": observers.accuracy.summary(),
    }


@app.get("/events")
def get_events(limit: int = Query(default=50, ge=1, le=200)):
    """Recent geofence and closest-approach events, newest first."""
    return observers.events.recent(limit)


@app.get("/geofences")
def get_geofences():
    return [fence.summary() for fence in observers.geofences]
