
import time
import requests
import calculator
from aircraft import Aircraft
from aircraft_tracker import AircraftTracker


def main():

    api = "https://opensky-network.org/api/states/all"
    params1 = {#Thess Park
            "lamin": 39.6,
            "lamax": 41.6,
            "lomin": 21.9,
            "lomax": 23.9
        }
    my_longitude = 22.9
    my_latitude = 40.6
    oAircraftTracker = AircraftTracker() #Class to handle all current aircrafts

    while True:

        response = requests.get(api, params=params1)
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
                    velocity = round(velocity*1.943834,1) #convert to knots

                    if callsign not in oAircraftTracker.aircrafts: #Checks if aircraft already exists
                        oAircraft = Aircraft(callsign, last_updated, longitude, latitude, altitude, heading, country_of_origin, velocity) #Creates new aircraft
                        oAircraftTracker.add_aircraft(oAircraft)
                    else:
                        oAircraft = oAircraftTracker.aircrafts[callsign]
                        oAircraft.update_info(longitude, latitude, last_updated,  altitude, heading, velocity) #Adds new aircraft to tracker list
                                            
                    print("Distnace Away: ", oAircraft.get_distance_from_user(my_longitude, my_latitude), " miles")
                    print()
                
            else:
                print("No Aircraft Found")

            oAircraftTracker.display() #shows all callsigns
            print("Iteration Completed")
            time.sleep(5)
        else:
            print("Connection failed: Status code {}".format(status_code))
    
            exit()

main()


'''
                    if len(history) >= 2 and len(history)>1:
                        num_points = min(len(history), 5)

                        old_time = history[-num_points][0]
                        old_distance = history[-num_points][1]

                        new_time = history[-1][0]
                        new_distance = history[-1][1]

                        time_difference = new_time - old_time
                        distance_difference = old_distance - new_distance

                        closing_speed = round(
                            3600 * distance_difference / time_difference
                        )
                    nearest_approach, na_time = calc.nearest_approach(bearing_angle_from_me,distance,heading,velocity)
                    aircraft_info = [callsign, distance, bearing_from_me, approaching, closing_speed, altitude, last_updated, nearest_approach, na_time]
                    aircrafts.append(aircraft_info)

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
                