"""
Replays a recorded OpenSky session as if it were live.

ReplayOpenSkyClient has the same interface as OpenSkyClient
(get_states, seconds_until_next_poll, authenticated, close), so the
polling loop, tracker, API and frontend run unchanged. Start one from
the dashboard's replay controls (see polling_service.py), or at startup
with:

    JACOBSKY_REPLAY=data/recordings/opensky_20261112_150600.jsonl \
        .venv/bin/uvicorn api:app

Optional: JACOBSKY_REPLAY_SPEED (default 1), JACOBSKY_REPLAY_START
(seconds into the recording to start at), JACOBSKY_REPLAY_LOOP=1.

All timestamps are shifted by a constant offset so the first frame
appears to have been received just now. Frames are then served on the
recorded schedule, so the gaps between responses (including any
rate-limit pauses during recording) are reproduced, except that gaps
longer than MAX_GAP_SECONDS are shortened.

At speeds other than 1 the replay's timestamps run faster than the
wall clock. sim_now() gives the replay's current time on that same
scale; the API reports it so the map can animate at the replay speed.
The speed can be changed while replaying (set_speed) without losing
the position in the recording.
"""

import logging
import statistics
import time

from flight_recording import load_recording

logger = logging.getLogger(__name__)

# Time positions (3) and last contact (4) in an OpenSky state array.
_TIME_INDICES = (3, 4)

# Longer gaps between frames (e.g. the recorder waiting out a rate
# limit) are shortened to this, so a replay doesn't sit idle for hours.
MAX_GAP_SECONDS = 300


class ReplayOpenSkyClient:
    authenticated = False

    def __init__(self, path, speed=1.0, start_offset_seconds=0.0, loop=False,
                 clock=time.time, max_gap_seconds=MAX_GAP_SECONDS):
        if speed <= 0:
            raise ValueError("Replay speed must be positive")

        recording = load_recording(path)
        first_time = recording.start_time if recording.frames else 0
        self._frames = [
            frame for frame in recording.frames
            if frame.time >= first_time + start_offset_seconds
        ]

        if not self._frames:
            raise ValueError(f"No frames to replay in {path}")

        self._path = path
        self._speed = speed
        self._loop = loop
        self._clock = clock
        self._index = 0
        # Set when the first frame is served. Replay time (the recording
        # timeline with long gaps cut, plus loop laps) advances from
        # _anchor_replay at _speed times the wall clock from _anchor_wall.
        self._anchor_wall = None
        self._anchor_replay = None
        # Constant added to replay time to make it look live at 1x.
        self._shift_offset = None

        # Replay time of each frame: the recorded time, minus whatever
        # was cut from earlier long gaps.
        gaps = [b.time - a.time for a, b in zip(self._frames, self._frames[1:])]
        self._times = [self._frames[0].time]
        for gap in gaps:
            self._times.append(self._times[-1] + min(gap, max_gap_seconds))
        self._first_time = self._times[0]

        # Recording time added each time the replay loops, so timestamps
        # keep increasing and the tracker accepts the next lap.
        typical_gap = statistics.median(gaps) if gaps else 15
        self._lap_length = self._times[-1] - self._first_time + typical_gap
        self._lap_offset = 0.0
        self._finished = False

        logger.info(
            "Replaying %s: %d frames, %.1f min of traffic, speed %gx%s",
            path,
            len(self._frames),
            (self._times[-1] - self._first_time) / 60,
            speed,
            ", looping" if loop else "",
        )

    def close(self):
        pass

    # --- speed, clock and progress ---------------------------------------

    @property
    def speed(self):
        return self._speed

    @property
    def path(self):
        return self._path

    @property
    def loop(self):
        return self._loop

    def set_speed(self, speed):
        """Change the speed, keeping the current position in the recording."""
        if speed <= 0:
            raise ValueError("Replay speed must be positive")

        if self._anchor_wall is not None:
            now = self._clock()
            self._anchor_replay = self._replay_time_at(now)
            self._anchor_wall = now

        self._speed = speed
        logger.info("Replay speed set to %gx", speed)

    def sim_now(self):
        """
        The replay's current time, on the same scale as the timestamps it
        serves. Before the first frame this is the wall clock.
        """
        now = self._clock()

        if self._anchor_wall is None:
            return now

        return self._replay_time_at(now) + self._shift_offset

    def progress(self):
        """Position in the recording, for display."""
        duration = self._times[-1] - self._first_time

        if self._anchor_wall is None:
            position = 0.0
        else:
            position = (
                self._replay_time_at(self._clock())
                - self._first_time
                - self._lap_offset
            )

        return {
            "position_seconds": round(min(max(position, 0.0), duration), 1),
            "duration_seconds": round(duration, 1),
            "frame_index": self._index,
            "frame_count": len(self._frames),
            "finished": self._finished,
        }

    def get_states(self, bounding_box=None):
        """Return the next recorded response, shifted to the present."""
        now = self._clock()

        if self._anchor_wall is None:
            self._anchor_wall = now
            self._anchor_replay = self._first_time
            self._shift_offset = now - self._first_time

        if self._index >= len(self._frames):
            if not self._loop:
                if not self._finished:
                    logger.info("Replay finished; aircraft will now time out")
                    self._finished = True
                # Keep time moving with no aircraft, so the missing-
                # aircraft command clears the map.
                return self._replay_time_at(now) + self._shift_offset, []

            self._index = 0
            self._lap_offset += self._lap_length
            logger.info("Replay looping to the start")

        frame = self._frames[self._index]
        # Same shift for the response and its states, so a cut gap moves
        # them together.
        offset = (
            self._shift_offset
            + self._lap_offset
            + self._times[self._index]
            - frame.time
        )
        self._index += 1

        return frame.time + offset, [
            self._shift_state(state, offset) for state in frame.states or []
        ]

    def seconds_until_next_poll(self):
        """Wall-clock seconds until the next recorded frame is due."""
        if self._anchor_wall is None:
            return 0.0  # nothing served yet

        if self._index >= len(self._frames) and not self._loop:
            return 15

        if self._index < len(self._frames):
            next_time = self._times[self._index] + self._lap_offset
        else:
            next_time = self._first_time + self._lap_offset + self._lap_length

        due = self._anchor_wall + (next_time - self._anchor_replay) / self._speed
        return max(0.0, due - self._clock())

    def _replay_time_at(self, wall_time):
        # Replay time, not recorded time, once gaps have been cut.
        return self._anchor_replay + (wall_time - self._anchor_wall) * self._speed

    @staticmethod
    def _shift_state(state, offset):
        if not isinstance(state, list):
            return state

        shifted = list(state)
        for index in _TIME_INDICES:
            if index < len(shifted) and isinstance(shifted[index], (int, float)) \
                    and not isinstance(shifted[index], bool):
                shifted[index] = shifted[index] + offset
        return shifted
