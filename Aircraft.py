

class Aircraft:

    def __init__(self, callsign, timestamp, longitude, latitude, altitude, heading, country_of_origin, velocity): #timestamp should be last updated
        self.callsign = callsign
        self.timestamp = timestamp
        self.longitude = longitude
        self.latitude = latitude
        self.altitude = altitude
        self.heading = heading
        self.country_of_origin = country_of_origin
        self.velocity = velocity
        self.location_history = {}

    def update_position(self, new_longitude, new_latitude, new_timestamp):
        self.longitude = new_longitude
        self.latitude = new_latitude
        self.timestamp = new_timestamp
        self.update_postition_history(new_timestamp, new_longitude, new_latitude)

    def update_postition_history(self, timestamp, longitude, latitude):
        if timestamp not in self.location_history:
            self.location_history[timestamp] = Position(longitude, latitude)
        self.location_history = sorted(self.location_history)


class Position:

    def __init__(self, longitude, latitude):
        self.longitude = longitude
        self.latitude = latitude
    
    
        