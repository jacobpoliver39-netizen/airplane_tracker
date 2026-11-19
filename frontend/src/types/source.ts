// Mirrors GET /source and GET /recordings in api.py.

export interface ReplayProgress {
  position_seconds: number;
  duration_seconds: number;
  frame_index: number;
  frame_count: number;
  finished: boolean;
}

export interface SourceStatus {
  mode: "live" | "replay";
  recording: string | null;
  speed: number;
  loop: boolean;
  progress: ReplayProgress | null;
  // Time the aircraft timestamps are on, and how fast it runs.
  clock: { now: number; speed: number };
}

export interface RecordingInfo {
  name: string;
  kind: "recording" | "csv";
  size_bytes: number;
  modified: number;
}
