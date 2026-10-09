
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
        self.distance_from_user = self.get_distance_from_user()
        self.location_history = {}
        print("Aircraft Created")
        self.update_location_history()#timestamp, longitude, latitude, self.distance_from_user

    def update_info(self, new_longitude, new_latitude, new_timestamp, new_altitude, new_heading, new_velocity):
        self.longitude = new_longitude
        self.latitude = new_latitude
        self.timestamp = new_timestamp
        self.altitude = new_altitude
        self.heading = new_heading
        self.velocity = new_velocity
        self.distance_from_user = self.get_distance_from_user()
        self.update_location_history()#new_timestamp, new_longitude, new_latitude, self.distance_from_user
        print("Aircraft Info Updated")

    def update_location_history(self):#, timestamp, longitude, latitude
        if self.timestamp not in self.location_history:
            self.location_history[self.timestamp] = Position(self.longitude, self.latitude, self.distance_from_user)
            print("History Updated")

    def get_distance_from_user(self):
        distance_from_user =  Calculator.calculate_haversine_distance(self.user_longitude, self.user_latitude, self.longitude, self.latitude)
        return distance_from_user

    def get_approach_speed_towards_user(self): #NOTE: Dictionary entries not necessarily in chronological order. Shouldn't affect average approach speed, though
        if (len(self.location_history.keys()) - 2) > 0:
            sum_of_approach_speeds = 0
            for i in range(len(self.location_history.keys()) - 2):
                newest_timestamp = list(self.location_history.keys())[-i]
                newest_distance = self.location_history[newest_timestamp].get_distance_from_user()
                second_newest_timestamp = list(self.location_history.keys())[-(i+1)]
                second_newest_distance = self.location_history[second_newest_timestamp].get_distance_from_user()
                difference_in_time = newest_timestamp - second_newest_timestamp
                difference_in_distance = second_newest_distance - newest_distance
                approach_speed = round(difference_in_distance/difference_in_time*3600,2)
                sum_of_approach_speeds += approach_speed
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
        pass

    def get_nearest_distance_time(self):
        pass

    def get_bearing_from_user(self):
        pass

    def get_info(self):
        info = []
        info.append(("Callsign: ", self.callsign))
        info.append(("Distance: ", self.get_distance_from_user(), " miles"))
        info.append(("Ave Approach Speed: ", self.get_approach_speed_towards_user(), " mph"))
        '''info.append(("Nearest Distance: ", self.get_nearest_distance_from_user(), " miles"))
        info.append(("Nearest Distance Time: ", self.get_nearest_distance_time(), " seconds"))
        info.append(("Bearing from User: ", self.get_bearing_from_user()))'''
        #for i in info:
            #print(i)
        return info


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


    
    
        