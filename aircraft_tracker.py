#class to calculate information about aircraft in relation to a given position

class AircraftTracker:

    def __init__(self):
        self.aircrafts = {} #list of all current aircrafts

    def add_aircraft(self, aircraft): #adds an aircraft to the list
        callsign = aircraft.callsign
        self.aircrafts[callsign] = aircraft
        print("Aircraft Added to List")

    def display_callsigns(self): #displays all current callsigns
        for callsign in self.aircrafts:
            print(callsign)

    def display_aircraft_info_nearest_to_farthest(self): #displays all current callsigns
        sorted_dict = self.sort_aircrafts_by_distance()
        for aircraft in sorted_dict.values():
            print(aircraft.get_info()) #FINISH THIS NEXT

    def sort_aircrafts_by_distance(self):
        sorted_aircraft_dict = dict(sorted(self.aircrafts.items(), key=lambda item: item[1].get_distance_from_user()))
        return sorted_aircraft_dict