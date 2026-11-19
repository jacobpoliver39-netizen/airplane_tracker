import logging
import time

import requests

import config
from aircraft_factory import AircraftFactory
from commands import RemoveLowAltitudeAircraftCommand, RemoveMissingAircraftCommand
from logging_service import LoggingService
from opensky_adapter import OpenSkyAdapter
from opensky_client import OpenSkyClient, OpenSkyRateLimitError
from tracker_state import aircraft_tracker

logger = logging.getLogger(__name__)

# Default adapter (OpenSky format -> AircraftObservation) and factory
# (AircraftObservation -> Aircraft) used by the polling loop.
default_adapter = OpenSkyAdapter()
default_factory = AircraftFactory(config.USER_LONGITUDE, config.USER_LATITUDE)


def is_trackable(observation, minimum_altitude=config.MINIMUM_ALTITUDE_FEET):
    """Return False for aircraft on the ground or below the minimum altitude."""
    if observation.on_ground:
        return False

    return observation.altitude is None or observation.altitude >= minimum_altitude


def apply_states(tracker, states, response_time, adapter=None, factory=None):
    """
    Update the tracker from one validated OpenSky response.

    Returns the number of aircraft observed in the response.
    """
    adapter = adapter if adapter is not None else default_adapter
    factory = factory if factory is not None else default_factory

    observations = adapter.to_observations(states)
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
                tracker.add_aircraft(factory.create(observation))

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
