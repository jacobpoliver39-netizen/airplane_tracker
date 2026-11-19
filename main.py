import logging
import time

import requests

import config
from aircraft_factory import AircraftFactory
from command_queue import TrackerWorker
from commands import (
    CommandBatch,
    RemoveLowAltitudeAircraftCommand,
    RemoveMissingAircraftCommand,
    UpdateAircraftCommand,
)
from logging_service import LoggingService
from opensky_adapter import OpenSkyAdapter
from opensky_client import OpenSkyClient, OpenSkyRateLimitError
from tracker_state import aircraft_tracker

logger = logging.getLogger(__name__)

# Default adapter (OpenSky format -> AircraftObservation) and factory
# (AircraftObservation -> Aircraft) used by the polling loop.
default_adapter = OpenSkyAdapter()
default_factory = AircraftFactory(config.USER_LONGITUDE, config.USER_LATITUDE)


def build_poll_commands(states, response_time, adapter=None, factory=None):
    """
    Turn one validated OpenSky response into the commands that apply it.

    Returns (batch, observed_count). The batch holds one
    UpdateAircraftCommand per valid state, then the missing-aircraft and
    low-altitude removals. Nothing touches the tracker here.
    """
    adapter = adapter if adapter is not None else default_adapter
    factory = factory if factory is not None else default_factory

    observations = adapter.to_observations(states)
    observed_callsigns = {observation.callsign for observation in observations}

    commands = [
        UpdateAircraftCommand(
            observation, factory, config.MINIMUM_ALTITUDE_FEET
        )
        for observation in observations
    ]
    commands.append(
        RemoveMissingAircraftCommand(
            observed_callsigns,
            current_time=response_time,
            grace_seconds=config.MISSING_AIRCRAFT_GRACE_SECONDS,
        )
    )
    commands.append(
        RemoveLowAltitudeAircraftCommand(config.MINIMUM_ALTITUDE_FEET)
    )

    batch = CommandBatch(commands, label=f"poll at {response_time}")

    return batch, len(observed_callsigns)


def apply_states(tracker, states, response_time, adapter=None, factory=None):
    """
    Build the commands for one response and execute them right away.

    Returns the number of aircraft observed in the response.
    """
    batch, observed = build_poll_commands(
        states, response_time, adapter=adapter, factory=factory
    )
    batch.execute(tracker)

    return observed


def poll_once(client, executor):
    """
    Producer step: fetch one OpenSky response and submit the commands
    that apply it.

    A failed or malformed request raises before any command is created.
    """
    response_time, states = client.get_states()

    if states is None:
        logger.info("OpenSky returned no aircraft states")

    batch, observed = build_poll_commands(states, response_time)
    executor.submit(batch)

    logger.info(
        "Polling cycle completed: %d aircraft observed, %d commands submitted",
        observed,
        len(batch),
    )


def _wait(stop_event, seconds):
    if stop_event is None:
        time.sleep(seconds)
    else:
        stop_event.wait(seconds)


def main(stop_event=None, client=None, tracker=aircraft_tracker, wait_first=False):
    """
    Poll `client` (OpenSky, or a replay from JACOBSKY_REPLAY) until
    stop_event is set. A client passed in is not closed here.

    wait_first: wait until the client's next poll is due before the
    first poll, used when resuming a replay that was already running.
    """
    LoggingService.initialize()

    owns_client = client is None
    client = client if client is not None else _create_client()

    # Consumer: the only thread that changes the tracker.
    worker = TrackerWorker(tracker).start()

    try:
        # Producer: this thread polls and submits commands.
        _poll_until_stopped(client, worker, stop_event, wait_first=wait_first)
    finally:
        # Applies anything still queued before returning.
        worker.stop()

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


def _poll_until_stopped(client, executor, stop_event, wait_first=False):
    logger.info(
        "Polling OpenSky every %d s (%s access)",
        config.POLL_INTERVAL_SECONDS,
        "authenticated" if client.authenticated else "anonymous",
    )

    if wait_first:
        _wait(stop_event, _next_wait_seconds(client))

    while stop_event is None or not stop_event.is_set():
        retry_after = None

        try:
            poll_once(client, executor)
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
