
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



@app.get("/aircraft")
def get_aircraft():
    aircraft_list = []

    for plane in aircraft_tracker.get_sorted_aircrafts().values():
        curved_approach = plane.get_curved_nearest_approach()
        aircraft_list.append({
            "id": plane.callsign,
            "callsign": plane.callsign,
            "latitude": plane.latitude,
            "longitude": plane.longitude,
            "altitude": plane.altitude,
            "speed": plane.velocity,
            "heading": plane.heading,
            "distance": plane.distance_from_user,
            "nearest_distance": plane.get_nearest_distance_from_user(),
            "nearest_distance_time": plane.get_nearest_distance_time(),
             "curved_nearest_distance": (
                curved_approach[0] if curved_approach is not None else None
            ),
            "curved_nearest_distance_time": (
                curved_approach[1] if curved_approach is not None else None
            ),
        })

    return aircraft_list

