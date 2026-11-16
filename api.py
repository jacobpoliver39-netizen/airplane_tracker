
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from main import main
from logging_service import LoggingService
from tracker_state import aircraft_tracker


@asynccontextmanager
async def lifespan(app: FastAPI):
    LoggingService.initialize()
    stop_event = threading.Event()
    polling_thread = threading.Thread(
        target=main,
        args=(stop_event,),
        daemon=True,
    )

    polling_thread.start()

    try:
        yield
    finally:
        stop_event.set()
        polling_thread.join(timeout=10)
        LoggingService.reset()


app = FastAPI(title="JacobSky API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_methods=["GET"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"message": "JacobSky API is running"}



TRAJECTORY_STEP_SECONDS = 5


def _round_or_none(value, digits=2):
    return None if value is None else round(value, digits)


def serialize_aircraft(plane):
    curved_approach = plane.get_curved_nearest_approach()

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
        "nearest_distance": _round_or_none(
            plane.get_nearest_distance_from_user()
        ),
        "nearest_distance_time": plane.get_nearest_distance_time(),
        "curved_nearest_distance": _round_or_none(curved_distance),
        "curved_nearest_distance_time": curved_time,
        # Position time (Unix seconds). Trajectory points start at this
        # position and are TRAJECTORY_STEP_SECONDS apart, which lets the
        # frontend animate each aircraft along its predicted path.
        "timestamp": plane.timestamp,
        "trajectory_step_seconds": TRAJECTORY_STEP_SECONDS,
        "straight_trajectory": plane.get_straight_trajectory(
            sample_interval_seconds=TRAJECTORY_STEP_SECONDS
        ),
        "curved_trajectory": plane.get_curved_trajectory(
            sample_interval_seconds=TRAJECTORY_STEP_SECONDS
        ),
    }


@app.get("/aircraft")
def get_aircraft():
    # Hold the tracker lock so the polling thread cannot change an
    # aircraft's history while it is being read.
    with aircraft_tracker.lock:
        return [
            serialize_aircraft(plane)
            for plane in aircraft_tracker.get_sorted_aircrafts().values()
        ]
