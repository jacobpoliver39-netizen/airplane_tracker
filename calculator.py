import math
class Calculator:

    @staticmethod
    def haversine(x):
        return math.pow(math.sin(x / 2), 2)

    @staticmethod
    def calculate_haversine_distance(lon1, lat1, lon2, lat2):
        lon1 = math.radians(lon1)
        lat1 = math.radians(lat1)
        lon2 = math.radians(lon2)
        lat2 = math.radians(lat2)
        hav_angle = Calculator.haversine(lat2 - lat1) + math.cos(lat1) * math.cos(lat2) * Calculator.haversine(lon2 - lon1)
        angle = math.asin(math.sqrt(hav_angle)) * 2
        distance_between = round(angle * 3959,2)
        return distance_between

    @staticmethod
    def bearing_angle_from_me(lat1, lon1, lat2, lon2):

        lat1 = math.radians(lat1)
        lon1 = math.radians(lon1)
        lat2 = math.radians(lat2)
        lon2 = math.radians(lon2)

        y = math.sin(lon2 - lon1) * math.cos(lat2)

        x = (
                math.cos(lat1) * math.sin(lat2)
                - math.sin(lat1) * math.cos(lat2) * math.cos(lon2 - lon1)
        )

        angle = math.degrees(math.atan2(y, x))

        return (angle + 360) % 360
    
    @staticmethod
    def bearing_from_me(angle):

        if 337.5 < angle or angle <= 22.5:
            return "North"
        elif 22.5 < angle <= 67.5:
            return "Northeast"
        elif 67.5 < angle <= 112.5:
            return "East"
        elif 112.5 < angle <= 157.5:
            return "Southeast"
        elif 157.5 < angle <= 202.5:
            return "South"
        elif 202.5 < angle <= 247.5:
            return "Southwest"
        elif 247.5 < angle <= 292.5:
            return "West"
        elif 292.5 < angle <= 337.5:
            return "Northwest"

    @staticmethod
    def approaching(bearing_from_me, heading):

        bearing_to_me = (bearing_from_me + 180) % 360

        difference = abs(heading - bearing_to_me)
        difference = min(difference, 360 - difference)

        if difference <= 45:
            return "Approaching You"
        elif difference >= 135:
            return "Flying Away From You"
        else:
            return "Flying Perpendicular to You"

    @staticmethod
    def nearest_approach(bearing_from_me, distance_from_me, heading, velocity):

        bearing_to_me = (bearing_from_me + 180) % 360

        theta = abs(bearing_to_me - heading)
        theta = min(theta, 360 - theta)

        theta = math.radians(theta)

        nearest_approach = distance_from_me * math.sin(theta)

        distance_to_nearest = distance_from_me * math.cos(theta)

        na_time = distance_to_nearest / velocity

        return nearest_approach, na_time

