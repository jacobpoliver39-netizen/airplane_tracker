// Backend URL. Override with VITE_API_URL in frontend/.env.local.
export const API_BASE_URL: string =
  import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000";

export const POLL_INTERVAL_MS = 5000;

// Keep in sync with USER_LATITUDE / USER_LONGITUDE in config.py.
export const USER_POSITION: [number, number] = [40.6, 23.0];
