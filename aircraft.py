
#Maybe add distance history? Heading History?

import logging

from calculator import Calculator

logger = logging.getLogger(__name__)

class Aircraft:

    def __init__(self, callsign, timestamp, longitude, latitude, altitude, heading, country_of_origin, velocity, user_longitude, user_latitude):
        self.callsign = callsign
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

    def update_info(self, new_longitude, new_latitude, new_timestamp, new_altitude, new_heading, new_velocity):
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
        positions = sorted(self.location_history.items())

        if len(positions) < 2:
            return "Not Enough Data"

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
            return "Not Enough Data"

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
        positions = sorted(self.location_history.items())[-2:]

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
        Capture straight-line and curved predictions from the
        aircraft's current state.
        """
        ground_motion = self.get_estimated_ground_motion()
        turn_rate = self.get_estimated_turn_rate()

        return {
            "timestamp": self.timestamp,
            "longitude": self.longitude,
            "latitude": self.latitude,
            "straight_speed": self.velocity,
            "straight_heading": self.heading,
            "ground_motion": ground_motion,
            "turn_rate": turn_rate,
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

        # Straight-line prediction using reported speed and heading.
        straight_displacement = Calculator.predict_ctrv_position(
            snapshot["straight_speed"],
            snapshot["straight_heading"],
            0,
            elapsed_seconds,
        )

        straight_longitude, straight_latitude = (
            Calculator.local_coordinates_to_gps(
                straight_displacement[0],
                straight_displacement[1],
                snapshot["longitude"],
                snapshot["latitude"],
            )
        )

        straight_error = Calculator.calculate_haversine_distance(
            straight_longitude,
            straight_latitude,
            actual_longitude,
            actual_latitude,
        )

        result = {
            "timestamp": snapshot["timestamp"],
            "elapsed_seconds": elapsed_seconds,
            "straight_error_miles": straight_error,
            "curved_error_miles": None,
        }

        # Curved prediction, only when the snapshot had enough history.
        ground_motion = snapshot["ground_motion"]
        turn_rate = snapshot["turn_rate"]

        if ground_motion is not None and turn_rate is not None:
            ground_speed, ground_track = ground_motion

            curved_displacement = Calculator.predict_ctrv_position(
                ground_speed,
                ground_track,
                turn_rate,
                elapsed_seconds,
            )

            curved_longitude, curved_latitude = (
                Calculator.local_coordinates_to_gps(
                    curved_displacement[0],
                    curved_displacement[1],
                    snapshot["longitude"],
                    snapshot["latitude"],
                )
            )

            result["curved_error_miles"] = (
                Calculator.calculate_haversine_distance(
                    curved_longitude,
                    curved_latitude,
                    actual_longitude,
                    actual_latitude,
                )
            )

        return result

    def get_curved_nearest_approach(self):
        """
        Estimate closest future distance using recent curved ground motion.
        Returns (distance_miles, time_seconds), or None if data is insufficient.
        """
        ground_motion = self.get_estimated_ground_motion()
        turn_rate = self.get_estimated_turn_rate()

        if ground_motion is None or turn_rate is None:
            return None

        ground_speed, ground_track = ground_motion

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
            speed_mph=ground_speed,
            ground_track_degrees=ground_track,
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
        Generate future GPS coordinates using the CTRV model.
        Returns a list of [latitude, longitude] pairs, or None
        if there is insufficient movement history.
        """
        ground_motion = self.get_estimated_ground_motion()
        turn_rate = self.get_estimated_turn_rate()

        if ground_motion is None or turn_rate is None:
            return None

        if (
            prediction_seconds < 0
            or sample_interval_seconds <= 0
        ):
            return None

        ground_speed, ground_track = ground_motion
        trajectory = []

        for elapsed_seconds in range(
            0,
            prediction_seconds + 1,
            sample_interval_seconds,
        ):
            displacement = Calculator.predict_ctrv_position(
                ground_speed,
                ground_track,
                turn_rate,
                elapsed_seconds,
            )

            if displacement is None:
                return None

            east, north = displacement

            longitude, latitude = (
                Calculator.local_coordinates_to_gps(
                    east,
                    north,
                    self.longitude,
                    self.latitude,
                )
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

    def get_info(self):
        info = []
        info.append(("Callsign: ", self.callsign))
        info.append(("Distance: ", self.get_distance_from_user(), " miles"))
        #info.append(("Ave Approach Speed: ", self.get_approach_speed_towards_user(), " mph"))
        #info.append(("Altitude: ", self.altitude, " ft"))
        #info.append(("Bearing from User: ", self.get_direction_from_user_to_plane()))
        #info.append(("Heading: ", self.heading))
        info.append(("Nearest Distance: ", self.get_nearest_distance_from_user(), " miles"))
        info.append(("Nearest Distance Time: ", self.get_nearest_distance_time(), " seconds"))

        return info


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




