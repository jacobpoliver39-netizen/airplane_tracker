export type LatLng = [number, number];

// Mirrors the dicts returned by GET /aircraft in api.py.
export interface Aircraft {
  id: string;
  callsign: string;
  // Lifecycle state (aircraft_state.py). "missing" = absent from recent
  // polls but still within the grace period; removed aircraft are not sent.
  state: "observed" | "missing";
  latitude: number;
  longitude: number;
  altitude: number | null;
  speed: number;
  heading: number;
  distance: number;
  nearest_distance: number;
  nearest_distance_time: number | null;
  curved_nearest_distance: number | null;
  curved_nearest_distance_time: number | null;
  // Unix seconds of the reported position. Trajectory points start at
  // that position and are trajectory_step_seconds apart.
  timestamp: number;
  trajectory_step_seconds: number;
  straight_trajectory: LatLng[] | null;
  curved_trajectory: LatLng[] | null;
}
