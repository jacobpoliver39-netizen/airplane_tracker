from aircraft import Aircraft
from observation import AircraftObservation


class AircraftFactory:
    """
    Creates Aircraft from provider-independent observations.

    A Simple Factory: one concrete class with a create() method. It is
    not the GoF Factory Method, which has subclasses override the
    creation step.

    Holds the user position every Aircraft is measured against, so
    callers only need the observation.
    """

    def __init__(self, user_longitude, user_latitude):
        self._user_longitude = user_longitude
        self._user_latitude = user_latitude

    def create(self, observation: AircraftObservation) -> Aircraft:
        return Aircraft(
            observation.callsign,
            observation.timestamp,
            observation.longitude,
            observation.latitude,
            observation.altitude,
            observation.heading,
            observation.country_of_origin,
            observation.velocity,
            self._user_longitude,
            self._user_latitude,
            on_ground=observation.on_ground,
        )
