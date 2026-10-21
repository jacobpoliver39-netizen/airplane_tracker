
#Maybe add distance history? Heading History?

from calculator import Calculator

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
        print("Velocity: ", self.velocity)
        self.user_longitude = user_longitude
        self.user_latitude = user_latitude
        self.distance_from_user = self.get_distance_from_user()
        self.location_history = {}
        self.bearing_from_user = self.get_bearing_from_user_to_plane()
        print("Aircraft Created")
        self.update_location_history()

    def update_info(self, new_longitude, new_latitude, new_timestamp, new_altitude, new_heading, new_velocity):
        self.longitude = new_longitude
        self.latitude = new_latitude
        self.timestamp = new_timestamp
        self.altitude = new_altitude
        self.heading = new_heading
        self.velocity = new_velocity
        self.distance_from_user = self.get_distance_from_user()
        self.bearing_from_user = self.get_bearing_from_user_to_plane()
        self.update_location_history()
        print("Aircraft Info Updated")

    def update_location_history(self):
        if self.timestamp not in self.location_history:
            self.location_history[self.timestamp] = Position(self.longitude, self.latitude, self.distance_from_user, self.heading, self.bearing_from_user)
            print("History Updated")

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


    def get_nearest_distance_from_user(self):
        return Calculator.nearest_approach(self.bearing_from_user, self.distance_from_user, self.heading)

    def get_nearest_distance_time(self):
        return Calculator.nearest_approach_time(self.bearing_from_user, self.distance_from_user, self.heading, self.velocity)

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




