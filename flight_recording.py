"""
Recording format for OpenSky sessions, used to replay past traffic.

A recording is a JSON Lines file. The first line is a header with the
settings the session ran under; every later line is one OpenSky
/states/all response, stored raw so a replay feeds exactly what the
live tracker would have seen:

    {"type": "header", "format": 1, "started_at": ..., "bounding_box": {...}, ...}
    {"type": "frame", "collected_at": 1794495960.4, "time": 1794495958, "states": [[...], ...]}

Each frame is flushed as soon as it is written, so a recording stopped
by Ctrl+C or a crash is still readable (a cut-off last line is skipped).
"""

import csv
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import config

logger = logging.getLogger(__name__)

FORMAT_VERSION = 1



@dataclass(frozen=True)
class Frame:
    """One recorded OpenSky response."""

    time: float  # OpenSky response time (Unix seconds)
    states: list | None
    collected_at: float | None = None  # local clock when it was received


@dataclass
class Recording:
    header: dict
    frames: list[Frame] = field(default_factory=list)

    @property
    def start_time(self):
        return self.frames[0].time

    @property
    def end_time(self):
        return self.frames[-1].time

    @property
    def duration_seconds(self):
        return self.end_time - self.start_time if self.frames else 0


def default_recording_path(now=None):
    now = now or datetime.now()
    return config.RECORDINGS_DIR / f"opensky_{now:%Y%m%d_%H%M%S}.jsonl"


class FlightRecorder:
    """Appends OpenSky responses to a recording file."""

    def __init__(self, path, header_extra=None):
        self.path = Path(path)
        self.frames_written = 0
        self.path.parent.mkdir(parents=True, exist_ok=True)

        is_new = not self.path.exists() or self.path.stat().st_size == 0
        self._file = self.path.open("a", encoding="utf-8")

        if is_new:
            header = {
                "type": "header",
                "format": FORMAT_VERSION,
                "started_at": datetime.now(UTC).isoformat(),
                "bounding_box": config.BOUNDING_BOX,
                "user_position": {
                    "longitude": config.USER_LONGITUDE,
                    "latitude": config.USER_LATITUDE,
                },
                "poll_interval_seconds": config.POLL_INTERVAL_SECONDS,
            }
            header.update(header_extra or {})
            self._write_line(header)

    def record(self, response_time, states, collected_at=None):
        if response_time is None:
            # OpenSky always sends "time"; fall back to the local clock.
            response_time = time.time()

        self._write_line({
            "type": "frame",
            "collected_at": collected_at if collected_at is not None else time.time(),
            "time": response_time,
            "states": states,
        })
        self.frames_written += 1

    def close(self):
        self._file.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()

    def _write_line(self, payload):
        self._file.write(json.dumps(payload, separators=(",", ":")) + "\n")
        self._file.flush()


def load_recording(path):
    """
    Read a recording file. Frames are returned sorted by response time,
    with duplicate responses (same time) dropped.
    """
    header = {}
    frames = []
    seen_times = set()

    with Path(path).open(encoding="utf-8") as recording_file:
        for line_number, line in enumerate(recording_file, start=1):
            line = line.strip()

            if not line:
                continue

            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                # Usually the last line of a recording that was killed
                # mid-write.
                logger.warning("Skipping unreadable line %d in %s", line_number, path)
                continue

            if entry.get("type") == "header":
                header = entry
            elif entry.get("type") == "frame" and entry.get("time") is not None:
                if entry["time"] in seen_times:
                    continue
                seen_times.add(entry["time"])
                frames.append(
                    Frame(
                        time=entry["time"],
                        states=entry.get("states"),
                        collected_at=entry.get("collected_at"),
                    )
                )

    frames.sort(key=lambda frame: frame.time)
    return Recording(header=header, frames=frames)


# --- import from the CSV written by collect_opensky.py -------------------

# CSV column -> OpenSky state index. Index 12 (sensors) is not in the CSV.
_CSV_STATE_COLUMNS = {
    "icao24": 0,
    "callsign": 1,
    "origin_country": 2,
    "time_position": 3,
    "last_contact": 4,
    "longitude": 5,
    "latitude": 6,
    "baro_altitude_m": 7,
    "on_ground": 8,
    "velocity_mps": 9,
    "true_track_deg": 10,
    "vertical_rate_mps": 11,
    "geo_altitude_m": 13,
    "squawk": 14,
    "spi": 15,
    "position_source": 16,
    "category": 17,
}
_INT_COLUMNS = {"time_position", "last_contact", "position_source", "category"}
_FLOAT_COLUMNS = {
    "longitude", "latitude", "baro_altitude_m", "velocity_mps",
    "true_track_deg", "vertical_rate_mps", "geo_altitude_m",
}
_BOOL_COLUMNS = {"on_ground", "spi"}


def _csv_value(column, text):
    if text is None or text == "":
        return None
    if column in _BOOL_COLUMNS:
        return text == "True"
    if column in _INT_COLUMNS:
        return int(float(text))
    if column in _FLOAT_COLUMNS:
        return float(text)
    return text


def convert_csv_to_recording(csv_path, output_path):
    """
    Turn the observations CSV from collect_opensky.py into a recording.

    The CSV only kept states that had a position, which are the only
    ones the tracker uses anyway. Returns the number of frames written.
    """
    frames = {}

    with Path(csv_path).open(newline="", encoding="utf-8") as csv_file:
        for row in csv.DictReader(csv_file):
            response_time = _csv_value("time_position", row["response_time"])

            if response_time is None:
                continue

            state = [None] * 18
            for column, index in _CSV_STATE_COLUMNS.items():
                state[index] = _csv_value(column, row.get(column))

            # Restore OpenSky's 8-character padded callsign.
            if state[1] is not None:
                state[1] = state[1].ljust(8)

            collected_at = datetime.fromisoformat(row["collected_at"]).timestamp()
            frames.setdefault(response_time, (collected_at, []))[1].append(state)

    with FlightRecorder(
        output_path, header_extra={"converted_from": str(csv_path)}
    ) as recorder:
        for response_time in sorted(frames):
            collected_at, states = frames[response_time]
            recorder.record(response_time, states, collected_at=collected_at)
        return recorder.frames_written
