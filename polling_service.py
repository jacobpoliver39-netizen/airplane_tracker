"""
Runs the polling loop in the background and lets the API switch its
data source while the server is running: live OpenSky, or a replay of
a recording at an adjustable speed.

Each switch stops the polling thread (whose TrackerWorker applies
anything still queued), swaps or adjusts the client, and starts the
loop again. Changing the source clears the tracker; changing the
replay speed keeps it and resumes from the same point.
"""

import logging
import threading
import time
from pathlib import Path

import config
import main
from flight_recording import convert_csv_to_recording
from opensky_client import OpenSkyClient
from replay_client import ReplayOpenSkyClient

logger = logging.getLogger(__name__)

MIN_REPLAY_SPEED = 0.25
MAX_REPLAY_SPEED = 120

# CSV files are converted to recordings here before replaying. It is a
# subfolder so the converted copies aren't listed as recordings too.
CSV_CACHE_DIRNAME = ".from_csv"

# A live poll can be waiting on an HTTP request this long before the
# thread notices it should stop.
_STOP_TIMEOUT_SECONDS = config.REQUEST_TIMEOUT_SECONDS + 10


class SourceBusyError(RuntimeError):
    """The previous polling thread did not stop in time."""


class RecordingNotFoundError(LookupError):
    pass


class PollingService:

    def __init__(
        self,
        tracker,
        live_client_factory=OpenSkyClient,
        replay_client_factory=ReplayOpenSkyClient,
        recordings_dir=config.RECORDINGS_DIR,
        data_dir=config.DATA_DIR,
    ):
        self._tracker = tracker
        self._live_client_factory = live_client_factory
        self._replay_client_factory = replay_client_factory
        self._recordings_dir = Path(recordings_dir)
        self._data_dir = Path(data_dir)

        # Serialises start/stop/switch calls from concurrent requests.
        self._lock = threading.RLock()
        self._client = None
        self._recording_name = None  # None while live
        self._thread = None
        self._stop_event = None

    # --- lifecycle -------------------------------------------------------

    def start(self):
        """Start with the source from config (JACOBSKY_REPLAY or live)."""
        with self._lock:
            if config.REPLAY_FILE:
                client = self._replay_client_factory(
                    config.REPLAY_FILE,
                    speed=config.REPLAY_SPEED,
                    start_offset_seconds=config.REPLAY_START_SECONDS,
                    loop=config.REPLAY_LOOP,
                )
                self._set_client(client, Path(config.REPLAY_FILE).name)
            else:
                self._set_client(self._live_client_factory(), None)

            self._start_thread()

    def stop(self):
        with self._lock:
            self._stop_thread()

            if self._client is not None:
                self._client.close()
                self._client = None

    # --- switching -------------------------------------------------------

    def start_replay(self, name, speed=1.0, loop=False):
        """Replay a recording (or collector CSV) listed by list_recordings."""
        _check_speed(speed)
        path = self._resolve_recording(name)

        # Load before stopping anything, so a bad file leaves the
        # current source running.
        client = self._replay_client_factory(str(path), speed=speed, loop=loop)

        with self._lock:
            self._stop_thread()
            self._replace_client(client, name)
            self._tracker.clear()
            self._start_thread()

        return self.status()

    def go_live(self):
        client = self._live_client_factory()

        with self._lock:
            self._stop_thread()
            self._replace_client(client, None)
            self._tracker.clear()
            self._start_thread()

        return self.status()

    def set_speed(self, speed):
        """Change the replay speed without restarting the recording."""
        _check_speed(speed)

        with self._lock:
            if not self.is_replaying:
                raise ValueError("Speed can only be changed during a replay")

            # Stopping wakes the loop from its wait, so the new speed
            # applies now rather than after the current gap.
            self._stop_thread()
            self._client.set_speed(speed)
            self._start_thread(wait_first=True)

        return self.status()

    # --- queries ---------------------------------------------------------

    @property
    def is_replaying(self):
        return self._client is not None and self._recording_name is not None

    def status(self):
        with self._lock:
            if not self.is_replaying:
                return {
                    "mode": "live",
                    "recording": None,
                    "speed": 1.0,
                    "loop": False,
                    "progress": None,
                    "clock": {"now": time.time(), "speed": 1.0},
                }

            client = self._client
            return {
                "mode": "replay",
                "recording": self._recording_name,
                "speed": client.speed,
                "loop": client.loop,
                "progress": client.progress(),
                "clock": {"now": client.sim_now(), "speed": client.speed},
            }

    def list_recordings(self):
        """Recordings (.jsonl) and collector CSVs that can be replayed."""
        entries = []

        for path in sorted(self._recordings_dir.glob("*.jsonl")):
            entries.append(_describe(path, "recording"))

        for path in sorted(self._data_dir.glob("*.csv")):
            entries.append(_describe(path, "csv"))

        return entries

    # --- internals -------------------------------------------------------

    def _resolve_recording(self, name):
        # Only names from the listing are accepted, never a client path.
        for path in self._recording_paths():
            if path.name == name:
                if path.suffix == ".csv":
                    return self._converted_csv(path)
                return path

        raise RecordingNotFoundError(f"No recording named {name!r}")

    def _recording_paths(self):
        yield from self._recordings_dir.glob("*.jsonl")
        yield from self._data_dir.glob("*.csv")

    def _converted_csv(self, csv_path):
        """Convert a collector CSV to a recording, reusing an up-to-date copy."""
        cache_dir = self._recordings_dir / CSV_CACHE_DIRNAME
        output = cache_dir / f"{csv_path.stem}.jsonl"

        if output.exists() and output.stat().st_mtime >= csv_path.stat().st_mtime:
            return output

        cache_dir.mkdir(parents=True, exist_ok=True)
        # Write to a temporary file so a failed conversion leaves no
        # half-written copy that looks up to date.
        temporary = output.with_suffix(".jsonl.tmp")
        temporary.unlink(missing_ok=True)
        frames = convert_csv_to_recording(csv_path, temporary)
        temporary.replace(output)
        logger.info("Converted %s to a recording (%d frames)", csv_path.name, frames)

        return output

    def _set_client(self, client, recording_name):
        self._client = client
        self._recording_name = recording_name

    def _replace_client(self, client, recording_name):
        old = self._client
        self._set_client(client, recording_name)

        if old is not None:
            old.close()

    def _start_thread(self, wait_first=False):
        self._stop_event = threading.Event()
        self._thread = threading.Thread(
            target=main.main,
            kwargs={
                "stop_event": self._stop_event,
                "client": self._client,
                "tracker": self._tracker,
                "wait_first": wait_first,
            },
            name="polling",
            daemon=True,
        )
        self._thread.start()

    def _stop_thread(self):
        if self._thread is None:
            return

        self._stop_event.set()
        self._thread.join(_STOP_TIMEOUT_SECONDS)

        if self._thread.is_alive():
            # Starting another loop now could let the old one write
            # stale aircraft after the tracker is cleared.
            raise SourceBusyError(
                "The polling thread is still busy; try again shortly"
            )

        self._thread = None
        self._stop_event = None


def _check_speed(speed):
    if not MIN_REPLAY_SPEED <= speed <= MAX_REPLAY_SPEED:
        raise ValueError(
            f"Speed must be between {MIN_REPLAY_SPEED} and {MAX_REPLAY_SPEED}"
        )


def _describe(path, kind):
    stat = path.stat()
    return {
        "name": path.name,
        "kind": kind,
        "size_bytes": stat.st_size,
        "modified": stat.st_mtime,
    }
