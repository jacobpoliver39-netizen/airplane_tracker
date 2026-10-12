
export interface Aircraft {
  id: string;
  callsign: string;
  latitude: number;
  longitude: number;
  altitude: number; // feet
  speed: number; // miles per hour
  heading: number; // degrees, 0–359
  distance: number; // statute miles
}
