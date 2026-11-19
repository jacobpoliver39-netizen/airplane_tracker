import logging
import math

from observation import AircraftObservation

logger = logging.getLogger(__name__)

METERS_TO_FEET = 3.28084
METERS_PER_SECOND_TO_MPH = 2.236936


def _is_number(value):
    """True for finite ints and floats (not bools, NaN or infinity)."""
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


class OpenSkyAdapter:
    """
    Adapter from OpenSky's /states/all format to AircraftObservation.

    This is the only place that knows OpenSky's positional state arrays
    and its units (metres, m/s). The rest of the system works with
    AircraftObservation in feet and mph.
    """

    def to_observations(self, states):
        """
        Convert a list of OpenSky state arrays to observations.

        Incomplete or malformed states are skipped.
        """
        observations = []
        skipped = 0

        for state in states or []:
            observation = self.parse_state(state)

            if observation is None:
                skipped += 1
            else:
                observations.append(observation)

        if skipped:
            logger.debug("Skipped %d incomplete OpenSky states", skipped)

        return observations

    @staticmethod
    def parse_state(state):
        """
        Convert one OpenSky state array to an AircraftObservation.

        Returns None for states without a callsign, without the fields
        the predictions need (position, position time, velocity, heading),
        with a non-finite number, or with a position or velocity out of
        range. The heading is normalised to [0, 360).
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

        if not (
            -90 <= latitude <= 90
            and -180 <= longitude <= 180
            and velocity >= 0
        ):
            return None

        altitude = state[7]
        altitude = (
            round(altitude * METERS_TO_FEET, 1) if _is_number(altitude) else None
        )

        return AircraftObservation(
            callsign=callsign.strip(),
            timestamp=timestamp,
            longitude=longitude,
            latitude=latitude,
            altitude=altitude,
            # Only a real JSON true counts; a missing value means airborne.
            on_ground=state[8] is True,
            velocity=round(velocity * METERS_PER_SECOND_TO_MPH, 2),
            heading=heading % 360,
            country_of_origin=state[2],
        )
