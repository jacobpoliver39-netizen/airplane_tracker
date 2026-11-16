import logging
import time
from dataclasses import dataclass

import requests

import config
from aircraft import Aircraft
from commands import RemoveLowAltitudeAircraftCommand, RemoveMissingAircraftCommand
from logging_service import LoggingService
from opensky_client import OpenSkyClient, OpenSkyRateLimitError
from tracker_state import aircraft_tracker

logger = logging.getLogger(__name__)

METERS_TO_FEET = 3.28084
METERS_PER_SECOND_TO_MPH = 2.236936


@dataclass(frozen=True)
class Observation:
    """One aircraft state from OpenSky, converted to tracker units."""

    callsign: str
    timestamp: float
    longitude: float
    latitude: float
    altitude: float | None  # feet, None when OpenSky has no altitude
    on_ground: bool
    velocity: float  # mph
    heading: float  # degrees
    country_of_origin: str | None


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def parse_state(state):
    """
    Convert one OpenSky state array to an Observation.

    Returns None for states without a callsign or without the fields
    the predictions need (position, position time, velocity, heading).
    Index layout: 1 callsign, 2 country, 3 time_position, 5 lon, 6 lat,
    7 baro altitude (m), 8 on_ground, 9 velocity (m/s), 10 true track.
    """
    if not isinstance(state, (list, tuple)) or len(state) < 11:
        return None

    callsign = state[1]

    if not isinstance(callsign, str) or not callsign.strip():
        return None

    timestamp = state[3]
    longitude = state[5]
    latitude = state[6]
    velocity = state[9]
    heading = state[10]

    if not all(
        _is_number(value)
        for value in (timestamp, longitude, latitude, velocity, heading)
    ):
        return None

    altitude = state[7]
    altitude = (
        round(altitude * METERS_TO_FEET, 1) if _is_number(altitude) else None
    )

    return Observation(
        callsign=callsign.strip(),
        timestamp=timestamp,
        longitude=longitude,
        latitude=latitude,
        altitude=altitude,
        on_ground=bool(state[8]),
        velocity=round(velocity * METERS_PER_SECOND_TO_MPH, 2),
        heading=heading,
        country_of_origin=state[2],
    )


def is_trackable(observation, minimum_altitude=config.MINIMUM_ALTITUDE_FEET):
    """Return False for aircraft on the ground or below the minimum altitude."""
    if observation.on_ground:
        return False

    return observation.altitude is None or observation.altitude >= minimum_altitude


def apply_states(tracker, states, response_time):
    """
    Update the tracker from one validated OpenSky response.

    Returns the number of aircraft observed in the response.
    """
    observations = []
    skipped = 0

    for state in states or []:
        observation = parse_state(state)

        if observation is None:
            skipped += 1
            continue

        observations.append(observation)

    if skipped:
        logger.debug("Skipped %d incomplete OpenSky states", skipped)

    observed_callsigns = {observation.callsign for observation in observations}

    with tracker.lock:
        for observation in observations:
            existing = tracker.aircrafts.get(observation.callsign)

            if existing is not None:
                # Update even when the aircraft is now low or on the
                # ground, so the low-altitude command removes it once.
                existing.update_info(
                    observation.longitude,
                    observation.latitude,
                    observation.timestamp,
                    observation.altitude,
                    observation.heading,
                    observation.velocity,
                    new_on_ground=observation.on_ground,
                )
            elif is_trackable(observation):
                tracker.add_aircraft(
                    Aircraft(
                        observation.callsign,
                        observation.timestamp,
                        observation.longitude,
                        observation.latitude,
                        observation.altitude,
                        observation.heading,
                        observation.country_of_origin,
                        observation.velocity,
                        config.USER_LONGITUDE,
                        config.USER_LATITUDE,
                        on_ground=observation.on_ground,
                    )
                )

        RemoveMissingAircraftCommand(
            tracker,
            observed_callsigns,
            current_time=response_time,
            grace_seconds=config.MISSING_AIRCRAFT_GRACE_SECONDS,
        ).execute()

        RemoveLowAltitudeAircraftCommand(
            tracker, config.MINIMUM_ALTITUDE_FEET
        ).execute()

    return len(observed_callsigns)


def poll_once(client, tracker):
    """
    Fetch one OpenSky response and apply it to the tracker.

    A failed or malformed request raises before the tracker is touched.
    """
    response_time, states = client.get_states()

    if states is None:
        logger.info("OpenSky returned no aircraft states")

    observed = apply_states(tracker, states, response_time)

    logger.info(
        "Polling cycle completed: %d aircraft observed, %d currently tracked",
        observed,
        len(tracker.aircrafts),
    )


def _wait(stop_event, seconds):
    if stop_event is None:
        time.sleep(seconds)
    else:
        stop_event.wait(seconds)


def main(stop_event=None, client=None, tracker=aircraft_tracker):
    LoggingService.initialize()

    owns_client = client is None
    client = client if client is not None else _create_client()

    try:
        _poll_until_stopped(client, tracker, stop_event)
    finally:
        if owns_client:
            client.close()


def _create_client():
    if config.REPLAY_FILE:
        # Imported here so live runs don't load the replay code.
        from replay_client import ReplayOpenSkyClient

        return ReplayOpenSkyClient(
            config.REPLAY_FILE,
            speed=config.REPLAY_SPEED,
            start_offset_seconds=config.REPLAY_START_SECONDS,
            loop=config.REPLAY_LOOP,
        )

    return OpenSkyClient()


def _poll_until_stopped(client, tracker, stop_event):
    logger.info(
        "Polling OpenSky every %d s (%s access)",
        config.POLL_INTERVAL_SECONDS,
        "authenticated" if client.authenticated else "anonymous",
    )

    while stop_event is None or not stop_event.is_set():
        retry_after = None

        try:
            poll_once(client, tracker)
        except OpenSkyRateLimitError as error:
            retry_after = error.retry_after_seconds
            logger.warning("%s", error)
        except (requests.RequestException, ValueError) as error:
            logger.warning("OpenSky request failed or returned invalid data: %s", error)
        except Exception:
            # Never let an unexpected error end the polling thread.
            logger.exception("Unexpected error during polling cycle")

        _wait(stop_event, _next_wait_seconds(client, retry_after))


def _next_wait_seconds(client, retry_after=None):
    """
    Ask the client how long to wait (fixed for OpenSky, the recorded gap
    for a replay). Asked after the poll, because a replay times the wait
    from the frame it just served.
    """
    try:
        wait_seconds = client.seconds_until_next_poll()
    except Exception:
        logger.exception("Could not get the next poll time")
        wait_seconds = config.POLL_INTERVAL_SECONDS

    if retry_after is not None:
        wait_seconds = max(wait_seconds, retry_after)
        logger.warning("Next attempt in %d s", wait_seconds)

    return wait_seconds


if __name__ == "__main__":
    main()
