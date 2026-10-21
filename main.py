
import time
import requests
import calculator
from aircraft import Aircraft
from tracker_state import aircraft_tracker

def main(stop_event=None):

    api = "https://opensky-network.org/api/states/all"
    params1 = {#Botsari
            "lamin": 39.6,
            "lamax": 41.6,
            "lomin": 21.9,
            "lomax": 23.9
        }

    params2 = {#ACT
                "lamin": 39.6,
                "lamax": 41.6,
                "lomin": 22.0,
                "lomax": 24.0
            }

    my_longitude = 23.0 #ACT Campus
    my_latitude = 40.6 #ACT Campus
    
    #my_longitude = 22.9 #Botsari
    #my_latitude = 40.6 #Botsari
    oAircraftTracker = aircraft_tracker #Class to handle all current aircrafts

    while stop_event is None or not stop_event.is_set():

        response = requests.get(api, params=params2)
        data = response.json()
        status_code = response.status_code

        if status_code == 200:
            print("Connected to API!")
            print()

            if data["states"] != None:
                for aircraft_data in data["states"]:
                    callsign = aircraft_data[1]
                    longitude = aircraft_data[5]
                    latitude = aircraft_data[6]
                    if aircraft_data[7]:
                        altitude = round(aircraft_data[7]*3.28084,1) #convert to ft
                    else:
                        altitude = 1
                    on_ground = aircraft_data[8]
                    velocity = aircraft_data[9]
                    heading = aircraft_data[10]
                    vertical_rate = aircraft_data[11]
                    country_of_origin = aircraft_data[2]
                    last_updated = aircraft_data[3]
                    velocity = round(velocity*2.236936, 2) #convert m/s to mph
                    if velocity == 0:
                        velocity = 1

                    if callsign not in oAircraftTracker.aircrafts: #Checks if aircraft already exists
                        oAircraft = Aircraft(callsign, last_updated, longitude, latitude, altitude, heading, country_of_origin, velocity, my_longitude, my_latitude) #Creates new aircraft
                        oAircraftTracker.add_aircraft(oAircraft)
                    else:
                        oAircraft = oAircraftTracker.aircrafts[callsign]
                        oAircraft.update_info(longitude, latitude, last_updated,  altitude, heading, velocity) #Adds new aircraft to tracker list
                                            
                    #oAircraft.get_info()
                    #print(oAircraftTracker.aircrafts.values())
                    print()
                
            else:
                print("No Aircraft Found")

            #oAircraftTracker.display_all_callsigns() #shows all callsigns
            oAircraftTracker.display_aircraft_info_nearest_to_farthest()
            print("Iteration Completed")
            if stop_event is None:
                time.sleep(15)
            else:
                stop_event.wait(15)
        else:
            print("Connection failed: Status code {}".format(status_code))
    
            exit()

if __name__ == "__main__":
    main()


'''
                    

                for callsign in aircrafts[0]:
                    if callsign not in current_callsigns and (data["time"] - last_updated) > 40:
                        try:
                            aircrafts.remove(data[callsign])
                            distance_history.remove(data[callsign])
                        except:
                            pass


                aircrafts.sort(key=lambda aircraft_info: aircraft_info[1])
                #callsigns = []
                for data in aircrafts:
                    #callsigns.append(aircraft[0])
                    print(data[0],"\n",data[1]," miles ", data[2], "\n",data[3], ", \nAlitude: ", data[5], "\nNearest approach: ",data[7], "miles in ",data[8]," seconds")
                    if data[4] == None:
                        print("No approach data\n")
                    elif data[4] > 0:
                        print("Closing at ", data[4], "miles per hour\n")
                    elif data[4] < 0:
                        print("Moving away at ", -data[4], "miles per hour\n")
                    elif data[4] == 0:
                        print("distance unchanged\n")




                print(distance_history)
'''
                