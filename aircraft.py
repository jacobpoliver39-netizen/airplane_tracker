
#Maybe add distance history? Heading History?

from calculator import Calculator

class Aircraft:

    def __init__(self, callsign, timestamp, longitude, latitude, altitude, heading, country_of_origin, velocity, user_longitude, user_latitude):
        self.callsign = callsign
        self.timestamp = timestamp #last update time
        self.longitude = longitude
        self.latitude = latitude
        self.altitude = altitude
        self.heading = heading
        self.country_of_origin = country_of_origin
        self.velocity = velocity
        self.user_longitude = user_longitude
        self.user_latitude = user_latitude
        self.distance_from_user = self.get_distance_from_user(self.user_longitude, self.user_latitude)
        self.location_history = {}
        print("Aircraft Created")
        self.update_position_history()#timestamp, longitude, latitude, self.distance_from_user

    def update_info(self, new_longitude, new_latitude, new_timestamp, new_altitude, new_heading, new_velocity):
        self.longitude = new_longitude
        self.latitude = new_latitude
        self.timestamp = new_timestamp
        self.altitude = new_altitude
        self.heading = new_heading
        self.velocity = new_velocity
        self.distance_from_user = self.get_distance_from_user(self.user_longitude, self.user_latitude)
        self.update_position_history()#new_timestamp, new_longitude, new_latitude, self.distance_from_user
        print("Aircraft Info Updated")

    def update_position_history(self):#, timestamp, longitude, latitude
        if self.timestamp not in self.location_history:
            self.location_history[self.timestamp] = Position(self.longitude, self.latitude, self.distance_from_user)
            print("History Updated")

    def get_distance_from_user(self, user_longitude, user_latitude):
        distance_from_user =  Calculator.calculate_haversine_distance(user_longitude, user_latitude, self.longitude, self.latitude)
        return distance_from_user

    def get_approach_speed_towards_user(self): #THIS FUNCTION IS WRONG. 
        change_in_distance = 
        count = 0
        for oPosition in self.location_history.values():
            sum_of_distances += oPosition.get_distance_from_user()
            count += 1
        ave_approach_speed = round(sum_of_distances/count, 2)
        return ave_approach_speed

    def get_nearest_distance_from_user(self):
        pass

    def get_nearest_distance_time(self):
        pass

    def get_bearing_from_user(self):
        pass

    def get_info(self):
        info = []
        info.append(("Callsign: ", self.callsign))
        info.append(("Distance: ", self.get_distance_from_user(self.user_longitude, self.user_latitude), " miles"))
        info.append(("Approach Speed: ", self.get_approach_speed_towards_user(), " mph"))
        '''info.append(("Nearest Distance: ", self.get_nearest_distance_from_user(), " miles"))
        info.append(("Nearest Distance Time: ", self.get_nearest_distance_time(), " seconds"))
        info.append(("Bearing from User: ", self.get_bearing_from_user()))'''
        for i in info:
            print(i)


class Position:

    def __init__(self, longitude, latitude, distance_from_user):
        self.longitude = longitude
        self.latitude = latitude
        self.distance_from_user = distance_from_user

    def get_longitude(self):
        return self.longitude

    def get_latitude(self):
        return self.latitude

    def get_distance_from_user(self):
        return self.distance_from_user


    
    
        