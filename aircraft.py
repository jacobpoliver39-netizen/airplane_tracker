import logging

from calculator import Calculator

logger = logging.getLogger(__name__)

class Aircraft:

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
        self.prediction_errors = []

    def update_info(self, new_longitude, new_latitude, new_timestamp, new_altitude, new_heading, new_velocity, new_on_ground=False):
        if new_timestamp > self.timestamp:
            snapshot = self.create_prediction_snapshot()

            result = self.evaluate_prediction_snapshot(
                snapshot,
                actual_timestamp=new_timestamp,
                actual_longitude=new_longitude,
                actual_latitude=new_latitude,
            )

            if result is not None:
                self.prediction_errors.append(result)
                self.prediction_errors = self.prediction_errors[-500:]

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

    def get_estimated_turn_rate(self):
        """Estimate recent ground-track turn rate in degrees per second."""
        positions = sorted(self.location_history.items())[-6:]

        observations = [
            (
                timestamp,
                position.get_longitude(),
                position.get_latitude(),
            )
            for timestamp, position in positions
        ]

        return Calculator.estimate_turn_rate(observations)

    def get_estimated_ground_motion(self):
        """Estimate current ground speed and track direction."""
        positions = sorted(self.location_history.items())[-6:]

        observations = [
            (
                timestamp,
                position.get_longitude(),
                position.get_latitude(),
            )
            for timestamp, position in positions
        ]

        return Calculator.estimate_ground_motion(observations)

    def create_prediction_snapshot(self):
        """
        Capture the state both predictions start from: the reported
        speed and heading, plus the estimated turn rate for the curve.
        """
        return {
            "timestamp": self.timestamp,
            "longitude": self.longitude,
            "latitude": self.latitude,
            "speed": self.velocity,
            "heading": self.heading,
            "turn_rate": self.get_estimated_turn_rate(),
        }

    def evaluate_prediction_snapshot(
        self,
        snapshot,
        actual_timestamp,
        actual_longitude,
        actual_latitude,
    ):
        """Compare saved predictions with a later observed position."""
        elapsed_seconds = actual_timestamp - snapshot["timestamp"]

        if elapsed_seconds <= 0:
            return None

        def prediction_error(turn_rate):
            displacement = Calculator.predict_ctrv_position(
                snapshot["speed"],
                snapshot["heading"],
                turn_rate,
                elapsed_seconds,
            )

            if displacement is None:
                return None

            longitude, latitude = Calculator.local_coordinates_to_gps(
                displacement[0],
                displacement[1],
                snapshot["longitude"],
                snapshot["latitude"],
            )

            return Calculator.calculate_haversine_distance(
                longitude, latitude, actual_longitude, actual_latitude
            )

        turn_rate = snapshot["turn_rate"]

        return {
            "timestamp": snapshot["timestamp"],
            "elapsed_seconds": elapsed_seconds,
            "straight_error_miles": prediction_error(0),
            # Curved prediction only when the snapshot had enough history.
            "curved_error_miles": (
                prediction_error(turn_rate) if turn_rate is not None else None
            ),
        }

    def get_curved_nearest_approach(self):
        """
        Estimate the closest future distance along the curved (CTRV) path.
        Returns (distance_miles, time_seconds), or None if there is not
        enough history or the closest point is outside the window.
        """
        turn_rate = self.get_estimated_turn_rate()

        if turn_rate is None:
            return None

        aircraft_east, aircraft_north = (
            Calculator.gps_to_local_coordinates(
                self.longitude,
                self.latitude,
                self.user_longitude,
                self.user_latitude,
            )
        )

        return Calculator.nearest_approach_ctrv(
            aircraft_east=aircraft_east,
            aircraft_north=aircraft_north,
            speed_mph=self.velocity,
            ground_track_degrees=self.heading,
            turn_rate_degrees_per_second=turn_rate,
            prediction_seconds=60,
            sample_interval_seconds=2,
        )

    def get_curved_trajectory(
        self,
        prediction_seconds=60,
        sample_interval_seconds=5,
    ):
        """
        Future [latitude, longitude] points along the curved (CTRV) path,
        one every sample_interval_seconds from the current position, or
        None if there is not enough history to estimate a turn rate.

        The path starts from the reported heading, which is the aircraft's
        current track. The history only supplies the turn rate: a track
        fitted to past positions lags behind a turning aircraft, which made
        the curve leave the aircraft at an angle.
        """
        turn_rate = self.get_estimated_turn_rate()

        if turn_rate is None:
            return None

        return self._sample_trajectory(
            turn_rate, prediction_seconds, sample_interval_seconds
        )

    def get_straight_trajectory(
        self,
        prediction_seconds=60,
        sample_interval_seconds=5,
    ):
        """
        Future [latitude, longitude] points along the reported heading at
        the reported speed, sampled like get_curved_trajectory().
        """
        return self._sample_trajectory(
            0, prediction_seconds, sample_interval_seconds
        )

    def _sample_trajectory(
        self,
        turn_rate,
        prediction_seconds,
        sample_interval_seconds,
    ):
        if prediction_seconds < 0 or sample_interval_seconds <= 0:
            return None

        trajectory = []

        for elapsed_seconds in range(
            0,
            prediction_seconds + 1,
            sample_interval_seconds,
        ):
            displacement = Calculator.predict_ctrv_position(
                self.velocity,
                self.heading,
                turn_rate,
                elapsed_seconds,
            )

            if displacement is None:
                return None

            longitude, latitude = Calculator.local_coordinates_to_gps(
                displacement[0],
                displacement[1],
                self.longitude,
                self.latitude,
            )

            trajectory.append([latitude, longitude])

        return trajectory

    def get_nearest_distance_from_user(self):
        return Calculator.nearest_approach(self.bearing_from_user, self.distance_from_user, self.heading)

    def get_nearest_distance_time(self):
        return Calculator.nearest_approach_time(self.bearing_from_user, self.distance_from_user, self.heading, self.velocity)

    
    def get_approach_status(self):
        """Classify the aircraft's current approach situation."""
        positions = sorted(self.location_history.items())

        # Check whether the aircraft was getting closer and
        # has now started moving farther away.
        if len(positions) >= 3:
            earlier_distance = positions[-3][1].get_distance_from_user()
            previous_distance = positions[-2][1].get_distance_from_user()
            current_distance = self.distance_from_user

            if (
                previous_distance < earlier_distance
                and current_distance > previous_distance
            ):
                return "passed"

        # If the geometry predicts a future closest point,
        # classify the aircraft as approaching.
        time_to_closest = self.get_nearest_distance_time()

        if time_to_closest is not None and time_to_closest > 0:
            return "approaching"

        return "moving_away"

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




