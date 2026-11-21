"""
Shared settings for the tracker, the API and the data collector.

Every setting lives here with an explicit default. Settings that can be
overridden by environment variables are read through the _env_* helpers,
which reject invalid values at startup with an error naming the
variable, instead of failing later or silently picking a meaning.
"""

import os
from pathlib import Path

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


def _env_text(name):
    """The variable's value with whitespace stripped, or None if unset/empty."""
    value = os.environ.get(name, "").strip()
    return value or None


def _env_number(name, default, convert, kind, minimum=None, maximum=None):
    text = _env_text(name)

    if text is None:
        return default

    try:
        value = convert(text)
    except ValueError:
        raise ValueError(f"{name} must be {kind}, got {text!r}") from None

    if (minimum is not None and value < minimum) or (
        maximum is not None and value > maximum
    ):
        bounds = (
            f"between {minimum} and {maximum}" if maximum is not None
            else f"at least {minimum}"
        )
        raise ValueError(f"{name} must be {bounds}, got {text!r}")

    return value


def _env_int(name, default, minimum=None, maximum=None):
    return _env_number(name, default, int, "a whole number", minimum, maximum)


def _env_float(name, default, minimum=None, maximum=None):
    return _env_number(name, default, float, "a number", minimum, maximum)


def _env_bool(name, default):
    text = _env_text(name)

    if text is None:
        return default
    if text.lower() in _TRUE:
        return True
    if text.lower() in _FALSE:
        return False

    raise ValueError(
        f"{name} must be one of {sorted(_TRUE | _FALSE)}, got {text!r}"
    )


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
OPENSKY_CLIENT_ID = _env_text("OPENSKY_CLIENT_ID")
OPENSKY_CLIENT_SECRET = _env_text("OPENSKY_CLIENT_SECRET")
OPENSKY_AUTHENTICATED = bool(OPENSKY_CLIENT_ID and OPENSKY_CLIENT_SECRET)

# OpenSky gives anonymous users 400 credits per day and registered
# users 4000. At one credit per request, these defaults stay under
# those limits for one running process (anonymous: 360/day,
# authenticated: 2880/day). Override with JACOBSKY_POLL_INTERVAL.
_DEFAULT_POLL_INTERVAL = 30 if OPENSKY_AUTHENTICATED else 15
POLL_INTERVAL_SECONDS = _env_int(
    "JACOBSKY_POLL_INTERVAL", _DEFAULT_POLL_INTERVAL, minimum=1
)

REQUEST_TIMEOUT_SECONDS = 20

# Larger OpenSky responses are rejected unread (the poll is skipped).
# A normal response for this area is well under 1 MB.
MAX_RESPONSE_BYTES = 10 * 1024 * 1024

# A position may not be timestamped more than this after the response
# that carries it; later ones are dropped as bad data (they would never
# expire).
MAX_TIMESTAMP_AHEAD_SECONDS = 120

# An aircraft missing from a response is kept until its last position
# report is older than this, so one missed poll does not drop it.
MISSING_AIRCRAFT_GRACE_SECONDS = POLL_INTERVAL_SECONDS + 30

# Aircraft on the ground or below this altitude (feet) are not tracked.
MINIMUM_ALTITUDE_FEET = 10

# Positions kept per aircraft; older ones are dropped. Predictions use
# only the last PREDICTION_HISTORY_WINDOW; 150 is about 37 minutes at a
# 15 s poll interval.
MAX_HISTORY_POSITIONS = 150

# How many recent positions the turn-rate and fitted-motion estimates use.
PREDICTION_HISTORY_WINDOW = 6

# Most aircraft one GET /aircraft response returns (the top ones by the
# selected ranking), so a crowded sky cannot overload the browser.
MAX_AIRCRAFT_PER_RESPONSE = 1000

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

# Where collect_opensky.py writes its CSV and record_opensky.py writes
# recordings. The dashboard lists both for replay.
DATA_DIR = Path(__file__).resolve().parent / "data"
RECORDINGS_DIR = DATA_DIR / "recordings"
OBSERVATIONS_CSV = DATA_DIR / "opensky_observations.csv"

# Replay speeds allowed from the dashboard and JACOBSKY_REPLAY_SPEED.
MIN_REPLAY_SPEED = 0.25
MAX_REPLAY_SPEED = 120

# Gaps between recorded frames longer than this (e.g. the recorder
# waiting out a rate limit) are shortened, so a replay doesn't sit idle.
REPLAY_MAX_GAP_SECONDS = 300

# Replay a recorded session (record_opensky.py) instead of polling
# OpenSky. Set JACOBSKY_REPLAY to the recording file.
REPLAY_FILE = _env_text("JACOBSKY_REPLAY")
REPLAY_SPEED = _env_float(
    "JACOBSKY_REPLAY_SPEED", 1.0, minimum=MIN_REPLAY_SPEED, maximum=MAX_REPLAY_SPEED
)
REPLAY_START_SECONDS = _env_float("JACOBSKY_REPLAY_START", 0.0, minimum=0)
REPLAY_LOOP = _env_bool("JACOBSKY_REPLAY_LOOP", False)
