#class to calculate information about aircraft in relation to a given position

class AircraftTracker:

    def __init__(self):
        self.aircrafts = {} #list of all current aircrafts

    def add_aircraft(self, aircraft): #adds an aircraft to the list
        callsign = aircraft.callsign
        self.aircrafts[callsign] = aircraft
        print("Aircraft Added to List")

    def display(self): #displays all current callsigns
        for callsign in self.aircrafts:
            print(callsign)

    