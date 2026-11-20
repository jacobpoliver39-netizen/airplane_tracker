import logging

from calculator import Calculator

logger = logging.getLogger(__name__)

class Aircraft:
    """
    One tracked aircraft: its current state, its position history, and
    values measured from them (distance, bearing, approach speed).

    Predictions (trajectories, nearest approach, accuracy scoring) live
    in trajectory_predictor.TrajectoryPredictor, and accuracy scores are
    collected by tracker_observers.PredictionAccuracyObserver.
    """

    def __init__(self, callsign, timestamp, longitude, latitude, altitude, heading, country_of_origin, velocity, user_longitude, user_latitude, on_ground=False):
        self.callsign = callsign
        self.on_ground = on_ground
        self.timestamp = timestamp
        self.longitude = longitude
        self.latitude = latitude
        self.altitude = altitude
        self.heading = heading
        self.country_of_origin = country_of_origin
        self.velocity = velocity
        logger.debug("%s initialized with velocity %.2f mph", self.callsign, self.velocity)
        self.user_longitude = user_longitude
        self.user_latitude = user_latitude
        self.distance_from_user = self.get_distance_from_user()
        self.location_history = {}
        self.bearing_from_user = self.get_bearing_from_user_to_plane()
        logger.debug("Aircraft created: %s", self.callsign)
        self.update_location_history()

    def update_info(self, new_longitude, new_latitude, new_timestamp, new_altitude, new_heading, new_velocity, new_on_ground=False):
        self.longitude = new_longitude
        self.latitude = new_latitude
        self.timestamp = new_timestamp
        self.altitude = new_altitude
        self.heading = new_heading
        self.velocity = new_velocity
        self.on_ground = new_on_ground
        self.distance_from_user = self.get_distance_from_user()
        self.bearing_from_user = self.get_bearing_from_user_to_plane()
        self.update_location_history()
        logger.debug("Aircraft information updated: %s", self.callsign)

    def update_location_history(self):
        if self.timestamp not in self.location_history:
            self.location_history[self.timestamp] = Position(self.longitude, self.latitude, self.distance_from_user, self.heading, self.bearing_from_user)
            logger.debug("Location history updated: %s", self.callsign)

    def get_distance_from_user(self):
        distance_from_user =  Calculator.calculate_haversine_distance(self.user_longitude, self.user_latitude, self.longitude, self.latitude)
        return distance_from_user

    def get_approach_speed_towards_user(self):
        """Average closing speed in mph, or None without enough history."""
        positions = sorted(self.location_history.items())

        if len(positions) < 2:
            return None

        approach_speeds = []

        for (earlier_time, earlier_position), (later_time, later_position) in zip(
            positions, positions[1:]
        ):
            difference_in_time = later_time - earlier_time

            if difference_in_time <= 0:
                continue

            difference_in_distance = (
                earlier_position.get_distance_from_user()
                - later_position.get_distance_from_user()
            )

            approach_speed = difference_in_distance / difference_in_time * 3600
            approach_speeds.append(approach_speed)

        if not approach_speeds:
            return None

        return round(sum(approach_speeds) / len(approach_speeds), 2)

    
    def get_closest_distance_so_far(self):
        """Return the smallest recorded distance from the user."""
        if not self.location_history:
            return self.distance_from_user

        return min(
            position.get_distance_from_user()
            for position in self.location_history.values()
        )

    def get_bearing_from_user_to_plane(self):
        return Calculator.bearing_angle_from_user_to_plane(self.longitude, self.latitude, self.user_longitude, self.user_latitude)

    def get_direction_from_user_to_plane(self):
        return Calculator.direction_of_plane_from_user(self.bearing_from_user)


class Position:

    def __init__(self, longitude, latitude, distance_from_user, heading, bearing_from_user):
        self.longitude = longitude
        self.latitude = latitude
        self.distance_from_user = distance_from_user
        self.heading = heading
        self.bearing_from_user = bearing_from_user

    def get_longitude(self):
        return self.longitude

    def get_latitude(self):
        return self.latitude

    def get_distance_from_user(self):
        return self.distance_from_user

    def get_heading(self):
        return self.heading

    def get_bearing_from_user(self):
        return self.bearing_from_user




