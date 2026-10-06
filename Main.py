import time

import requests
import math
import Calculator

api = "https://opensky-network.org/api/states/all"
params1 = {#my house
        "lamin": 42.0,
        "lamax": 43.2,
        "lomin": -74.4,
        "lomax": -73.2
    }
params2 = {#ALB
    "lamin": 42.55,
    "lamax": 42.95,
    "lomin": -75.00,
    "lomax": -73.60
}

my_latitude = 42.667
my_longitude =-73.8021

distance_history = {}

while True:
    current_callsigns = []
    aircrafts = []
    response = requests.get(api, params=params1)
    status_code = response.status_code


    if status_code == 200:
        print("Connected to API!")
        data = response.json()
        #print(data)

        calc = Calculator.Calculator()
        print(data["time"])
        print()
        if data["states"] != None:
            for aircraft in data["states"]:
                closing_speed = None
                callsign = aircraft[1]
                current_callsigns.append(callsign)
                longitude = aircraft[5]
                latitude = aircraft[6]
                altitude = round(aircraft[7]*3.28084,1)
                on_ground = aircraft[8]
                velocity = aircraft[9]
                heading = aircraft[10]
                vertical_rate = aircraft[11]
                country_of_origin = aircraft[2]
                last_updated = aircraft[3]
                distance = calc.distance_between(my_latitude, my_longitude, latitude, longitude)
                velocity = round(velocity*1.943834,1)
                velocity = velocity/3600
                bearing_angle_from_me = calc.bearing_angle_from_me(my_latitude, my_longitude, latitude, longitude)
                bearing_from_me = calc.bearing_from_me(bearing_angle_from_me)
                approaching = calc.approaching(bearing_angle_from_me, heading)

                '''
                print("Call sign:", callsign)
                print("Distance:", distance,"miles")
                print("Latitude:", latitude)
                print("Longitude:", longitude)
                print("Altitude: {} ft".format(round(altitude*3.28084,1)))
                print("On ground:", on_ground)
                print("Velocity: {} knots".format(velocity))
                print("Heading: {}\N{DEGREE SIGN}".format(round(heading,1)))
                print("Vertical Rate: ", round(vertical_rate*3.280833,1),"ft per sec")
                print("Country of Origin:", country_of_origin)
                print("Last Updated:", last_updated)'''
                #print()
                #print("Heading: {}\N{DEGREE SIGN}".format(round(heading, 1)))


                if callsign in distance_history and distance_history[callsign][len(distance_history[callsign])-1][0] != last_updated:
                    distance_history[callsign].append([last_updated,distance])
                elif callsign in distance_history:
                    pass
                else:
                    distance_history[callsign] = [[last_updated,distance]]

                distance_history[callsign].sort(key=lambda x: x[0])
                history = distance_history[callsign]

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
                        aircrafts.remove(aircraft[callsign])
                        distance_history.remove(aircraft[callsign])
                    except:
                        pass


            aircrafts.sort(key=lambda aircraft_info: aircraft_info[1])
            #callsigns = []
            for aircraft in aircrafts:
                #callsigns.append(aircraft[0])
                print(aircraft[0],"\n",aircraft[1]," miles ", aircraft[2], "\n",aircraft[3], ", \nAlitude: ", aircraft[5], "\nNearest approach: ",aircraft[7], "miles in ",aircraft[8]," seconds")
                if aircraft[4] == None:
                    print("No approach data\n")
                elif aircraft[4] > 0:
                    print("Closing at ", aircraft[4], "miles per hour\n")
                elif aircraft[4] < 0:
                    print("Moving away at ", -aircraft[4], "miles per hour\n")
                elif aircraft[4] == 0:
                    print("distance unchanged\n")




            print(distance_history)

            time.sleep(5)


        else:
            print("No Aircraft Found")

    else:
        print("Connection failed: Status code {}".format(status_code))

        exit()



