
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
        self.update_location_history()
        print("Aircraft Info Updated")

    def update_location_history(self):
        if self.timestamp not in self.location_history:
            self.location_history[self.timestamp] = Position(self.longitude, self.latitude, self.distance_from_user, self.heading, self.bearing_from_user)
            print("History Updated")

    def get_distance_from_user(self):
        distance_from_user =  Calculator.calculate_haversine_distance(self.user_longitude, self.user_latitude, self.longitude, self.latitude)
        return distance_from_user

    def get_approach_speed_towards_user(self): #NOTE: Dictionary entries not necessarily in chronological order. Shouldn't affect average approach speed, though
        if (len(self.location_history.keys()) - 2) > 0:
            sum_of_approach_speeds = 0
            count = 0
            for i in range(len(self.location_history.keys()) - 2):
                newest_timestamp = list(self.location_history.keys())[-i]
                newest_distance = self.location_history[newest_timestamp].get_distance_from_user()
                second_newest_timestamp = list(self.location_history.keys())[-(i+1)]
                second_newest_distance = self.location_history[second_newest_timestamp].get_distance_from_user()
                difference_in_time = newest_timestamp - second_newest_timestamp
                difference_in_distance = second_newest_distance - newest_distance
                approach_speed = round(difference_in_distance/difference_in_time*3600,2)
                sum_of_approach_speeds += approach_speed
                count += count
                if self.distance_from_user < 3 and count > 2: #FIX LATER; Very makeshift solution
                    break
            ave_approach_speed = round(sum_of_approach_speeds/(len(self.location_history.keys()) - 2), 2)   
            return ave_approach_speed
                    
        elif len(self.location_history.keys()) > 1:
            newest_timestamp = list(self.location_history.keys())[-1]
            newest_distance = self.location_history[newest_timestamp].get_distance_from_user()
            second_newest_timestamp = list(self.location_history.keys())[-2]
            second_newest_distance = self.location_history[second_newest_timestamp].get_distance_from_user()
            difference_in_time = newest_timestamp - second_newest_timestamp
            difference_in_distance = second_newest_distance - newest_distance
            ave_approach_speed = round(difference_in_distance/difference_in_time*3600,2)
            return ave_approach_speed
        
        else:
            return "Not Enough Data"
        
    
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


    
    
        