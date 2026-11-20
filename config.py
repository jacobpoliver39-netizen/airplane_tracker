"""Shared settings for the tracker, the API and the data collector."""

import os

# User position: ACT Campus, Thessaloniki.
# Alternative location (Botsari): longitude 22.9, latitude 40.6.
USER_LONGITUDE = 23.0
USER_LATITUDE = 40.6

# OpenSky bounding box around the user. A box of 25 square degrees
# or less costs one API credit per request.
BOUNDING_BOX = {
    "lamin": 39.6,
    "lamax": 41.6,
    "lomin": 22.0,
    "lomax": 24.0,
}

OPENSKY_STATES_URL = "https://opensky-network.org/api/states/all"
OPENSKY_TOKEN_URL = (
    "https://auth.opensky-network.org/auth/realms/opensky-network"
    "/protocol/openid-connect/token"
)

# Optional OAuth2 client credentials from the OpenSky account page.
OPENSKY_CLIENT_ID = os.environ.get("OPENSKY_CLIENT_ID")
OPENSKY_CLIENT_SECRET = os.environ.get("OPENSKY_CLIENT_SECRET")
OPENSKY_AUTHENTICATED = bool(OPENSKY_CLIENT_ID and OPENSKY_CLIENT_SECRET)

# OpenSky gives anonymous users 400 credits per day and registered
# users 4000. At one credit per request, these defaults stay under
# those limits for one running process (anonymous: 360/day,
# authenticated: 2880/day). Override with JACOBSKY_POLL_INTERVAL.
_DEFAULT_POLL_INTERVAL = 30 if OPENSKY_AUTHENTICATED else 15
POLL_INTERVAL_SECONDS = int(
    os.environ.get("JACOBSKY_POLL_INTERVAL", _DEFAULT_POLL_INTERVAL)
)

REQUEST_TIMEOUT_SECONDS = 20

# Larger OpenSky responses are rejected unread (the poll is skipped).
# A normal response for this area is well under 1 MB.
MAX_RESPONSE_BYTES = 10 * 1024 * 1024

# An aircraft missing from a response is kept until its last position
# report is older than this, so one missed poll does not drop it.
MISSING_AIRCRAFT_GRACE_SECONDS = POLL_INTERVAL_SECONDS + 30

# Aircraft on the ground or below this altitude (feet) are not tracked.
MINIMUM_ALTITUDE_FEET = 10

# Circular geofences watched by GeofenceObserver (enter/exit events).
GEOFENCES = [
    {
        "name": "ACT Campus",
        "longitude": USER_LONGITUDE,
        "latitude": USER_LATITUDE,
        "radius_miles": 5.0,
    },
]

# ClosestApproachObserver only reports passes at least this close.
CLOSEST_APPROACH_REPORT_MILES = 10.0

# Where collect_opensky.py writes CSVs and record_opensky.py writes
# recordings. The dashboard lists both for replay.
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
RECORDINGS_DIR = os.path.join(DATA_DIR, "recordings")

# Replay a recorded session (record_opensky.py) instead of polling
# OpenSky. Set JACOBSKY_REPLAY to the recording file.
REPLAY_FILE = os.environ.get("JACOBSKY_REPLAY") or None
REPLAY_SPEED = float(os.environ.get("JACOBSKY_REPLAY_SPEED", 1))
REPLAY_START_SECONDS = float(os.environ.get("JACOBSKY_REPLAY_START", 0))
REPLAY_LOOP = os.environ.get("JACOBSKY_REPLAY_LOOP", "") not in ("", "0", "false")
