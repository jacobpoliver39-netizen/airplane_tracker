
export interface Aircraft {
  id: string;
  callsign: string;
  latitude: number;
  longitude: number;
  altitude: number;
  speed: number;
  heading: number;
  distance: number;
  nearest_distance: number;
  nearest_distance_time: number | null;
}
