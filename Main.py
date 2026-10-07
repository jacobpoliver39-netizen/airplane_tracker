import time

import requests
import math
import Calculator
import Aircraft

api = "https://opensky-network.org/api/states/all"
params1 = {#Thess Park
        "lamin": 38.6,
        "lamax": 42.6,
        "lomin": 20.9,
        "lomax": 24.9
    }

#40.607216013970245, 22.955351468293287

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
            for data in data["states"]:
                closing_speed = None
                callsign = data[1]
                current_callsigns.append(callsign)
                longitude = data[5]
                latitude = data[6]
                if data[7]:
                    altitude = round(data[7]*3.28084,1)
                else:
                    altitude = 40000
                on_ground = data[8]
                velocity = data[9]
                heading = data[10]
                vertical_rate = data[11]
                country_of_origin = data[2]
                last_updated = data[3]
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

            time.sleep(5)


        else:
            print("No Aircraft Found")

    else:
        print("Connection failed: Status code {}".format(status_code))

        exit()


class New_Main_Class:

    api = "https://opensky-network.org/api/states/all"
    params1 = {#Thess Park
            "lamin": 38.6,
            "lamax": 42.6,
            "lomin": 20.9,
            "lomax": 24.9
        }

    while True:
        aircrafts = []
        response = requests.get(api, params=params1)
        status_code = response.status_code


        if status_code == 200:
            print("Connected to API!")
            data = response.json()
            
            print()
            if data["states"] != None:
                for data in data["states"]:
                    callsign = data[1]
                    longitude = data[5]
                    latitude = data[6]
                    if data[7]:
                        altitude = round(data[7]*3.28084,1) #convert to ft
                    else:
                        altitude = 40000
                    on_ground = data[8]
                    velocity = data[9]
                    heading = data[10]
                    vertical_rate = data[11]
                    country_of_origin = data[2]
                    last_updated = data[3]
                    velocity = round(velocity*1.943834,1) #convert to mph
                    velocity = velocity/3600

                    aircraft = Aircraft(callsign, last_updated, longitude, latitude, altitude, heading, country_of_origin, velocity)


                    
            

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

                time.sleep(5)


            else:
                print("No Aircraft Found")

        else:
            print("Connection failed: Status code {}".format(status_code))

            exit()

