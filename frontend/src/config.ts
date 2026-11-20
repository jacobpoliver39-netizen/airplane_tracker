// Backend URL. Override with VITE_API_URL in frontend/.env.local.
export const API_BASE_URL: string =
  import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000";

export const POLL_INTERVAL_MS = 5000;

// Polled faster during a replay, which can run up to 60x: the predicted
// paths cover 60 s, so slower polls would leave planes parked at their
// path ends between updates.
export const REPLAY_POLL_INTERVAL_MS = 500;

// Keep in sync with USER_LATITUDE / USER_LONGITUDE in config.py.
export const USER_POSITION: [number, number] = [40.6, 23.0];

// Prediction accuracy and events change slowly; refresh them less often.
export const INSIGHTS_POLL_INTERVAL_MS = 2000;
