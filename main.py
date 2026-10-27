
import time
import requests
import calculator
from aircraft import Aircraft
from tracker_state import aircraft_tracker
from commands import RemoveMissingAircraftCommand

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

        
        try:
            response = requests.get(api, params=params2, timeout=20)
            response.raise_for_status()
            data = response.json()

            # Validate the response before changing the tracker.
            if not isinstance(data, dict) or "states" not in data:
                raise ValueError("Unexpected OpenSky response structure")

            states = data["states"]

            if states is not None:
                if not isinstance(states, list):
                    raise ValueError("OpenSky states must be a list or null")

                if any(
                    not isinstance(aircraft_data, (list, tuple))
                    or len(aircraft_data) < 12
                    for aircraft_data in states
                ):
                    raise ValueError("Malformed aircraft state in response")

        except (requests.RequestException, ValueError) as error:
            print(f"OpenSky request failed or returned invalid data: {error}")

            if stop_event is None:
                time.sleep(15)
            else:
                stop_event.wait(15)

            continue


        if states is not None:
            observed_callsigns = set()

            for aircraft_data in states:
                callsign = aircraft_data[1]

                # Ignore empty callsigns for tracking purposes.
                if not callsign or not callsign.strip():
                    continue

                callsign = callsign.strip()
                observed_callsigns.add(callsign)

                longitude = aircraft_data[5]
                latitude = aircraft_data[6]

                if aircraft_data[7]:
                    altitude = round(aircraft_data[7] * 3.28084, 1)
                else:
                    altitude = 1

                on_ground = aircraft_data[8]
                velocity = aircraft_data[9]
                heading = aircraft_data[10]
                vertical_rate = aircraft_data[11]
                country_of_origin = aircraft_data[2]
                last_updated = aircraft_data[3]

                velocity = round(velocity * 2.236936, 2)
                if velocity == 0:
                    velocity = 1

                if callsign not in oAircraftTracker.aircrafts:
                    oAircraft = Aircraft(
                        callsign,
                        last_updated,
                        longitude,
                        latitude,
                        altitude,
                        heading,
                        country_of_origin,
                        velocity,
                        my_longitude,
                        my_latitude,
                    )
                    oAircraftTracker.add_aircraft(oAircraft)
                else:
                    oAircraft = oAircraftTracker.aircrafts[callsign]
                    oAircraft.update_info(
                        longitude,
                        latitude,
                        last_updated,
                        altitude,
                        heading,
                        velocity,
                    )

            command = RemoveMissingAircraftCommand(
                oAircraftTracker, observed_callsigns
            )
            command.execute()

        else:
            print("No Aircraft Found")
            command = RemoveMissingAircraftCommand(
                oAircraftTracker, set()
            )
            command.execute()


        #oAircraftTracker.display_all_callsigns() #shows all callsigns
        oAircraftTracker.display_aircraft_info_nearest_to_farthest()
        print("Iteration Completed")
        if stop_event is None:
            time.sleep(15)
        else:
            stop_event.wait(15)

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
                