
import csv
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

import config
from opensky_client import OpenSkyClient, OpenSkyRateLimitError


OUTPUT_FILE = (
    Path(__file__).resolve().parent
    / "data"
    / "opensky_observations.csv"
)

FIELDNAMES = [
    "collected_at",
    "response_time",
    "icao24",
    "callsign",
    "origin_country",
    "time_position",
    "last_contact",
    "longitude",
    "latitude",
    "baro_altitude_m",
    "on_ground",
    "velocity_mps",
    "true_track_deg",
    "vertical_rate_mps",
    "geo_altitude_m",
    "squawk",
    "spi",
    "position_source",
    "category",
]


def get_field(state, index):
    """Return an OpenSky state field, or None if unavailable."""
    return state[index] if len(state) > index else None


def collect():
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    file_exists = OUTPUT_FILE.exists() and OUTPUT_FILE.stat().st_size > 0

    client = OpenSkyClient()

    logging.info("Saving observations to %s", OUTPUT_FILE)
    logging.info(
        "Polling interval: %s seconds (%s access)",
        config.POLL_INTERVAL_SECONDS,
        "authenticated" if client.authenticated else "anonymous",
    )

    try:
        with OUTPUT_FILE.open("a", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(
                csv_file,
                fieldnames=FIELDNAMES,
            )

            if not file_exists:
                writer.writeheader()
                csv_file.flush()

            while True:
                cycle_start = time.monotonic()
                wait_override = None

                try:
                    response_time, states = client.get_states()
                    collected_at = datetime.now(timezone.utc).isoformat()
                    rows_written = 0

                    for state in states or []:
                        if not isinstance(state, (list, tuple)):
                            continue

                        longitude = get_field(state, 5)
                        latitude = get_field(state, 6)

                        if longitude is None or latitude is None:
                            continue

                        callsign = get_field(state, 1)

                        writer.writerow({
                            "collected_at": collected_at,
                            "response_time": response_time,
                            "icao24": get_field(state, 0),
                            "callsign": (
                                callsign.strip()
                                if isinstance(callsign, str) and callsign
                                else None
                            ),
                            "origin_country": get_field(state, 2),
                            "time_position": get_field(state, 3),
                            "last_contact": get_field(state, 4),
                            "longitude": longitude,
                            "latitude": latitude,
                            "baro_altitude_m": get_field(state, 7),
                            "on_ground": get_field(state, 8),
                            "velocity_mps": get_field(state, 9),
                            "true_track_deg": get_field(state, 10),
                            "vertical_rate_mps": get_field(state, 11),
                            "geo_altitude_m": get_field(state, 13),
                            "squawk": get_field(state, 14),
                            "spi": get_field(state, 15),
                            "position_source": get_field(state, 16),
                            "category": get_field(state, 17),
                        })

                        rows_written += 1

                    csv_file.flush()

                    logging.info(
                        "Collected %d aircraft observations",
                        rows_written,
                    )

                except OpenSkyRateLimitError as error:
                    logging.warning("%s", error)
                    wait_override = error.retry_after_seconds

                except (requests.RequestException, ValueError) as error:
                    logging.warning("OpenSky collection failed: %s", error)

                elapsed = time.monotonic() - cycle_start
                wait_time = max(0, config.POLL_INTERVAL_SECONDS - elapsed)

                if wait_override is not None:
                    wait_time = max(wait_time, wait_override)

                time.sleep(wait_time)
    finally:
        client.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
    )

    try:
        collect()
    except KeyboardInterrupt:
        logging.info("Collector stopped.")
