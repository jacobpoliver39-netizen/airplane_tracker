import math


class Calculator:

    @staticmethod
    def haversine(x):
        return math.pow(math.sin(x / 2), 2)

    @staticmethod
    def calculate_haversine_distance(lon1, lat1, lon2, lat2):
        lon1 = math.radians(lon1)
        lat1 = math.radians(lat1)
        lon2 = math.radians(lon2)
        lat2 = math.radians(lat2)
        hav_angle = Calculator.haversine(lat2 - lat1) + math.cos(lat1) * math.cos(lat2) * Calculator.haversine(lon2 - lon1)
        angle = math.asin(math.sqrt(hav_angle)) * 2
        distance_between = round(angle * 3959,2)
        return distance_between

    @staticmethod
    def gps_to_local_coordinates(
        longitude,
        latitude,
        reference_longitude,
        reference_latitude,
    ):
        """
        Convert GPS coordinates to local east/north distances in miles.
        Suitable for relatively short distances.
        """
        earth_radius_miles = 3959

        latitude_radians = math.radians(reference_latitude)

        delta_longitude = math.radians(
            longitude - reference_longitude
        )
        delta_latitude = math.radians(
            latitude - reference_latitude
        )

        east = (
            earth_radius_miles
            * delta_longitude
            * math.cos(latitude_radians)
        )

        north = earth_radius_miles * delta_latitude

        return east, north

    
    @staticmethod
    def local_coordinates_to_gps(
        east,
        north,
        reference_longitude,
        reference_latitude,
    ):
        """
        Convert local east/north distances in miles back to GPS coordinates.
        Uses the same local equirectangular approximation as
        gps_to_local_coordinates().
        """
        earth_radius_miles = 3959

        latitude_radians = math.radians(reference_latitude)

        latitude = reference_latitude + math.degrees(
            north / earth_radius_miles
        )

        longitude = reference_longitude + math.degrees(
            east / (
                earth_radius_miles * math.cos(latitude_radians)
            )
        )

        return longitude, latitude


    @staticmethod
    def bearing_angle_from_user_to_plane(plane_lon, plane_lat, user_lon, user_lat):

        lon1 = math.radians(user_lon)
        lat1 = math.radians(user_lat)
        lon2 = math.radians(plane_lon)
        lat2 = math.radians(plane_lat)

        y = math.sin(lon2 - lon1) * math.cos(lat2)

        x = (
                math.cos(lat1) * math.sin(lat2)
                - math.sin(lat1) * math.cos(lat2) * math.cos(lon2 - lon1)
        )

        angle = math.degrees(math.atan2(y, x))

        return (angle + 360) % 360


    @staticmethod
    def angular_difference(new_angle, old_angle):
        """Return the shortest signed angular change in degrees."""
        return (new_angle - old_angle + 180) % 360 - 180


    @staticmethod
    def estimate_turn_rate(
        observations,
        max_gap_seconds=60,
        min_segment_distance_miles=0.05,
    ):
        """
        Estimate signed ground-track turn rate in degrees per second.

        observations: chronological (timestamp, longitude, latitude) tuples.
        Positive rates indicate clockwise turns.
        """
        if len(observations) < 3:
            return None

        segments = []

        for earlier, later in zip(observations, observations[1:]):
            earlier_time, earlier_lon, earlier_lat = earlier
            later_time, later_lon, later_lat = later

            elapsed = later_time - earlier_time

            if elapsed <= 0 or elapsed > max_gap_seconds:
                continue

            distance = Calculator.calculate_haversine_distance(
                earlier_lon, earlier_lat, later_lon, later_lat
            )

            if distance < min_segment_distance_miles:
                continue

            bearing = Calculator.bearing_angle_from_user_to_plane(
                later_lon, later_lat, earlier_lon, earlier_lat
            )

            midpoint_time = (earlier_time + later_time) / 2

            segments.append((midpoint_time, bearing))

        turn_rates = []

        for earlier, later in zip(segments, segments[1:]):
            earlier_time, earlier_bearing = earlier
            later_time, later_bearing = later

            elapsed = later_time - earlier_time

            if elapsed <= 0:
                continue

            angle_change = Calculator.angular_difference(
                later_bearing, earlier_bearing
            )

            turn_rates.append(angle_change / elapsed)

        if not turn_rates:
            return None

        turn_rates.sort()
        middle = len(turn_rates) // 2

        if len(turn_rates) % 2 == 0:
            return (
                turn_rates[middle - 1] + turn_rates[middle]
            ) / 2

        return turn_rates[middle]


    @staticmethod
    def estimate_ground_motion(
        observations,
        max_gap_seconds=60,
        min_segment_distance_miles=0.05,
    ):
        """
        Estimate ground speed and direction from the latest GPS interval.

        Returns (speed_mph, ground_track_degrees), or None if the
        latest interval is invalid.
        """
        if len(observations) < 2:
            return None

        earlier, later = observations[-2:]

        earlier_time, earlier_lon, earlier_lat = earlier
        later_time, later_lon, later_lat = later

        elapsed = later_time - earlier_time

        if elapsed <= 0 or elapsed > max_gap_seconds:
            return None

        distance = Calculator.calculate_haversine_distance(
            earlier_lon,
            earlier_lat,
            later_lon,
            later_lat,
        )

        if distance < min_segment_distance_miles:
            return None

        ground_speed = distance / elapsed * 3600

        ground_track = Calculator.bearing_angle_from_user_to_plane(
            later_lon,
            later_lat,
            earlier_lon,
            earlier_lat,
        )

        return ground_speed, ground_track


    @staticmethod
    def predict_ctrv_position(
        speed_mph,
        ground_track_degrees,
        turn_rate_degrees_per_second,
        elapsed_seconds,
    ):
        """
        Predict east/north displacement using a Constant Turn Rate
        and Velocity model.

        Returns (east_miles, north_miles), relative to the starting
        position. Positive turn rates indicate clockwise turns.
        """
        if (
            speed_mph is None
            or ground_track_degrees is None
            or turn_rate_degrees_per_second is None
            or elapsed_seconds is None
        ):
            return None

        if speed_mph < 0 or elapsed_seconds < 0:
            return None

        # Convert to consistent units.
        speed = speed_mph / 3600
        track = math.radians(ground_track_degrees)
        turn_rate = math.radians(turn_rate_degrees_per_second)

        # Straight-line motion when the turn rate is effectively zero.
        if abs(turn_rate) < 1e-9:
            east = speed * elapsed_seconds * math.sin(track)
            north = speed * elapsed_seconds * math.cos(track)

            return east, north

        final_track = track + turn_rate * elapsed_seconds

        east = (
            speed / turn_rate
            * (math.cos(track) - math.cos(final_track))
        )

        north = (
            speed / turn_rate
            * (math.sin(final_track) - math.sin(track))
        )

        return east, north

    @staticmethod
    def nearest_approach_ctrv(
        aircraft_east,
        aircraft_north,
        speed_mph,
        ground_track_degrees,
        turn_rate_degrees_per_second,
        prediction_seconds=60,
        sample_interval_seconds=2,
    ):
        """
        Predict the closest distance to the reference point using CTRV.

        Aircraft position is expressed in local east/north miles.
        Returns (minimum_distance_miles, time_seconds).
        """
        if (
            speed_mph is None
            or ground_track_degrees is None
            or turn_rate_degrees_per_second is None
            or speed_mph < 0
            or prediction_seconds < 0
            or sample_interval_seconds <= 0
        ):
            return None

        closest_distance = float("inf")
        closest_time = None

        sample_times = range(
            0,
            prediction_seconds + 1,
            sample_interval_seconds,
        )

        for elapsed_seconds in sample_times:
            displacement = Calculator.predict_ctrv_position(
                speed_mph,
                ground_track_degrees,
                turn_rate_degrees_per_second,
                elapsed_seconds,
            )

            if displacement is None:
                return None

            predicted_east = aircraft_east + displacement[0]
            predicted_north = aircraft_north + displacement[1]

            distance = math.hypot(
                predicted_east,
                predicted_north,
            )

            if distance < closest_distance:
                closest_distance = distance
                closest_time = elapsed_seconds

        return closest_distance, closest_time

    @staticmethod
    def direction_of_plane_from_user(angle):

        if 337.5 < angle or angle <= 22.5:
            return "North"
        elif 22.5 < angle <= 67.5:
            return "Northeast"
        elif 67.5 < angle <= 112.5:
            return "East"
        elif 112.5 < angle <= 157.5:
            return "Southeast"
        elif 157.5 < angle <= 202.5:
            return "South"
        elif 202.5 < angle <= 247.5:
            return "Southwest"
        elif 247.5 < angle <= 292.5:
            return "West"
        elif 292.5 < angle <= 337.5:
            return "Northwest"

    @staticmethod
    def approaching(bearing_from_me, heading):

        bearing_to_me = (bearing_from_me + 180) % 360

        difference = abs(heading - bearing_to_me)
        difference = min(difference, 360 - difference)

        if difference <= 45:
            return "Approaching You"
        elif difference >= 135:
            return "Flying Away From You"
        else:
            return "Flying Perpendicular to You"

    @staticmethod
    def nearest_approach(bearing_from_me, distance_from_me, heading):
        bearing_to_me = (bearing_from_me + 180) % 360

        theta = abs(bearing_to_me - heading)
        theta = min(theta, 360 - theta)
        theta = math.radians(theta)

        # If the aircraft is moving away, its closest future
        # point is its current position.
        if theta >= math.pi / 2:
            return round(distance_from_me, 2)

        return round(distance_from_me * math.sin(theta), 2)

    @staticmethod
    def nearest_approach_time(
        bearing_from_me, distance_from_me, heading, velocity
    ):
        if velocity is None or velocity <= 0:
            return None

        bearing_to_me = (bearing_from_me + 180) % 360

        theta = abs(bearing_to_me - heading)
        theta = min(theta, 360 - theta)
        theta = math.radians(theta)

        # No future closest-approach event if the plane is
        # moving away or perpendicular to us.
        if theta >= math.pi / 2:
            return None

        distance_to_nearest = distance_from_me * math.cos(theta)

        return round((distance_to_nearest / velocity) * 3600, 2)