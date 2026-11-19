from dataclasses import dataclass


@dataclass(frozen=True)
class AircraftObservation:
    """
    One aircraft position report in tracker units, independent of the
    data provider. Adapters (e.g. OpenSkyAdapter) produce these, and
    AircraftFactory turns them into Aircraft objects.
    """

    callsign: str
    timestamp: float
    longitude: float
    latitude: float
    altitude: float | None  # feet, None when the provider has no altitude
    on_ground: bool
    velocity: float  # mph
    heading: float  # degrees
    country_of_origin: str | None
