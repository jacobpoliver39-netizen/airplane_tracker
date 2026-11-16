"""
Record a long OpenSky session for later replay.

    python record_opensky.py                      # record until Ctrl+C
    python record_opensky.py --hours 6            # stop after 6 hours
    python record_opensky.py -o data/recordings/evening.jsonl
    python record_opensky.py --from-csv data/opensky_observations.csv

Replay a recording through the normal tracker and API with
JACOBSKY_REPLAY=<file> (see replay_client.py).

The recorder spends API credits like the live tracker does, so don't
run both at once unless you have the quota for it.
"""

import argparse
import logging
import time

import requests

import config
from flight_recording import (
    FlightRecorder,
    convert_csv_to_recording,
    default_recording_path,
)
from opensky_client import OpenSkyClient, OpenSkyRateLimitError

logger = logging.getLogger("record_opensky")


def record(output_path, duration_seconds=None, client=None, sleep=time.sleep):
    owns_client = client is None
    client = client if client is not None else OpenSkyClient()
    deadline = (
        time.monotonic() + duration_seconds if duration_seconds else None
    )

    logger.info("Recording to %s", output_path)
    logger.info(
        "Polling every %d s (%s access)%s",
        config.POLL_INTERVAL_SECONDS,
        "authenticated" if client.authenticated else "anonymous",
        f", for {duration_seconds / 3600:g} h" if duration_seconds else "",
    )

    try:
        with FlightRecorder(
            output_path, header_extra={"authenticated": client.authenticated}
        ) as recorder:
            while deadline is None or time.monotonic() < deadline:
                cycle_start = time.monotonic()
                wait_seconds = config.POLL_INTERVAL_SECONDS

                try:
                    response_time, states = client.get_states()
                    recorder.record(response_time, states)
                    logger.info(
                        "Frame %d: %d states",
                        recorder.frames_written,
                        len(states or []),
                    )
                except OpenSkyRateLimitError as error:
                    if error.retry_after_seconds is not None:
                        wait_seconds = max(wait_seconds, error.retry_after_seconds)
                    logger.warning("%s; next attempt in %d s", error, wait_seconds)
                except (requests.RequestException, ValueError) as error:
                    logger.warning("OpenSky request failed: %s", error)

                elapsed = time.monotonic() - cycle_start
                wait_seconds = max(0, wait_seconds - elapsed)

                if deadline is not None:
                    wait_seconds = min(wait_seconds, max(0, deadline - time.monotonic()))

                sleep(wait_seconds)

            return recorder.frames_written
    finally:
        if owns_client:
            client.close()


def _parse_args():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "-o", "--output",
        help="recording file (default: data/recordings/opensky_<date_time>.jsonl)",
    )
    parser.add_argument(
        "--hours", type=float,
        help="stop after this many hours (default: run until Ctrl+C)",
    )
    parser.add_argument(
        "--from-csv", metavar="CSV",
        help="convert a collect_opensky.py CSV into a recording instead of polling",
    )
    return parser.parse_args()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
    )
    args = _parse_args()
    output = args.output or default_recording_path()

    if args.from_csv:
        written = convert_csv_to_recording(args.from_csv, output)
        logger.info("Wrote %d frames to %s", written, output)
    else:
        try:
            record(output, duration_seconds=args.hours * 3600 if args.hours else None)
        except KeyboardInterrupt:
            logger.info("Recording stopped; saved to %s", output)
