#class to calculate information about aircraft in relation to a given position

class Aircraft_Tracker:

    def __init__(self):
        self.aircrafts = {}

    def add_aircraft(self, callsign, aircraft):
        self.aircrafts[callsign] = aircraft