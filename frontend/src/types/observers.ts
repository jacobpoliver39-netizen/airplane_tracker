// Mirrors GET /stats (prediction_accuracy), GET /events and GET /geofences
// in api.py, produced by the observers in tracker_observers.py.

export interface ErrorSummary {
  count: number;
  mean_miles: number;
  median_miles: number;
}

export type AccuracySegment = "all" | "turning" | "straight";

export interface PredictionAccuracy {
  scored_updates: number;
  turning_threshold_deg_per_s: number;
  // segment -> strategy name ("straight", "curved", "historical") -> errors
  segments: Record<AccuracySegment, Record<string, ErrorSummary>>;
}

export interface StatsResponse {
  prediction_accuracy: PredictionAccuracy;
}

export type TrackerEventType =
  | "geofence_enter"
  | "geofence_exit"
  | "closest_approach";

export interface TrackerEvent {
  id: number;
  type: TrackerEventType;
  callsign: string;
  time: number; // Unix seconds of the aircraft's position (replay time in a replay)
  latitude: number;
  longitude: number;
  altitude: number | null;
  distance_miles: number;
  geofence?: string;
  reason?: string; // why a geofence exit happened by removal
  closest_time?: number;
}

export interface Geofence {
  name: string;
  latitude: number;
  longitude: number;
  radius_miles: number;
  aircraft_inside: string[];
}
