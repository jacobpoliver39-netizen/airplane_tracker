

class Aircraft:

    def __init__(self, callsign, timestamp, longitude, latitude, altitude, heading, country_of_origin, velocity):
        self.callsign = callsign
        self.timestamp = timestamp #last update time
        self.longitude = longitude
        self.latitude = latitude
        self.altitude = altitude
        self.heading = heading
        self.country_of_origin = country_of_origin
        self.velocity = velocity
        self.location_history = {}
        print("Aircraft Created")
        self.update_position_history(timestamp, longitude, latitude)

    def update_info(self, new_longitude, new_latitude, new_timestamp, new_altitude, new_heading, new_velocity):
        self.longitude = new_longitude
        self.latitude = new_latitude
        self.timestamp = new_timestamp
        self.altitude = new_altitude
        self.heading = new_heading
        self.velocity = new_velocity
        self.update_position_history(new_timestamp, new_longitude, new_latitude)
        print("Aircraft Info Updated")

    def update_position_history(self, timestamp, longitude, latitude):
        if timestamp not in self.location_history:
            self.location_history[timestamp] = Position(longitude, latitude)
            print("History Updated")


class Position:

    def __init__(self, longitude, latitude):
        self.longitude = longitude
        self.latitude = latitude
    
    
        