
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from main import main
from tracker_state import aircraft_tracker


@asynccontextmanager
async def lifespan(app: FastAPI):
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
        aircraft_list.append({
            "id": plane.callsign,
            "callsign": plane.callsign,
            "latitude": plane.latitude,
            "longitude": plane.longitude,
            "altitude": plane.altitude,
            "speed": plane.velocity,
            "heading": plane.heading,
            "distance": plane.distance_from_user,
        })

    return aircraft_list
