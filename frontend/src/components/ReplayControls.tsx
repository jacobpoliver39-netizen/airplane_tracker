import { useEffect, useState } from "react";
import { API_BASE_URL } from "../config";
import type { RecordingInfo, SourceStatus } from "../types/source";

// Must stay within MIN_REPLAY_SPEED..MAX_REPLAY_SPEED in polling_service.py.
const SPEEDS = [1, 2, 5, 10, 30, 60];

interface ReplayControlsProps {
  source: SourceStatus | null;
  // Called with the new status after a successful switch.
  onSourceChange: (source: SourceStatus) => void;
}

function formatDuration(seconds: number): string {
  const total = Math.max(0, Math.round(seconds));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  const mmss = `${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
  return hours > 0 ? `${hours}:${mmss}` : mmss;
}

function formatSize(bytes: number): string {
  return bytes >= 1_000_000
    ? `${(bytes / 1_000_000).toFixed(1)} MB`
    : `${Math.max(1, Math.round(bytes / 1000))} kB`;
}

async function post(path: string, body?: unknown): Promise<SourceStatus> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const data = await response.json();
      if (typeof data?.detail === "string") detail = data.detail;
    } catch {
      // Keep the generic message.
    }
    throw new Error(detail);
  }

  return (await response.json()) as SourceStatus;
}

export default function ReplayControls({
  source,
  onSourceChange,
}: ReplayControlsProps) {
  const [recordings, setRecordings] = useState<RecordingInfo[]>([]);
  const [selected, setSelected] = useState("");
  const [speed, setSpeed] = useState(1);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const replaying = source?.mode === "replay";

  // Load the list once; it only changes when a new recording is made.
  useEffect(() => {
    let isMounted = true;

    fetch(`${API_BASE_URL}/recordings`)
      .then((response) => (response.ok ? response.json() : []))
      .then((data: RecordingInfo[]) => {
        if (!isMounted || !Array.isArray(data)) return;
        setRecordings(data);
        setSelected((current) => current || data[0]?.name || "");
      })
      .catch(() => {
        // The API being down is already shown by the status badge.
      });

    return () => {
      isMounted = false;
    };
  }, []);

  // While replaying, show the server's speed; otherwise the speed the
  // next replay will start at.
  const activeSpeed = replaying ? source.speed : speed;

  const run = async (action: () => Promise<SourceStatus>) => {
    setBusy(true);
    setError(null);
    try {
      onSourceChange(await action());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(false);
    }
  };

  const startReplay = () =>
    run(() => post("/source/replay", { recording: selected, speed: activeSpeed }));

  const changeSpeed = (value: number) => {
    setSpeed(value);
    if (replaying) {
      run(() => post("/source/replay/speed", { speed: value }));
    }
  };

  const goLive = () => run(() => post("/source/live"));

  const progress = source?.progress ?? null;
  const percent =
    progress && progress.duration_seconds > 0
      ? (progress.position_seconds / progress.duration_seconds) * 100
      : 0;

  return (
    <div className="replay-bar">
      <div className="filter-control replay-recording">
        <label htmlFor="replay-recording">RECORDING</label>
        <select
          id="replay-recording"
          value={selected}
          disabled={busy || recordings.length === 0}
          onChange={(event) => setSelected(event.target.value)}
        >
          {recordings.length === 0 && <option value="">No recordings found</option>}
          {recordings.map((recording) => (
            <option key={recording.name} value={recording.name}>
              {recording.name} ({recording.kind === "csv" ? "CSV, " : ""}
              {formatSize(recording.size_bytes)})
            </option>
          ))}
        </select>
      </div>

      <button
        className="replay-button replay-button--primary"
        disabled={busy || !selected}
        onClick={startReplay}
      >
        {replaying ? "↻ Restart replay" : "▶ Replay"}
      </button>

      <div className="replay-speeds" role="group" aria-label="Replay speed">
        <span className="replay-label">SPEED</span>
        <div className="replay-speed-buttons">
          {SPEEDS.map((value) => (
            <button
              key={value}
              className={`replay-speed${activeSpeed === value ? " replay-speed--active" : ""}`}
              aria-pressed={activeSpeed === value}
              disabled={busy}
              onClick={() => changeSpeed(value)}
            >
              {value}×
            </button>
          ))}
        </div>
      </div>

      {replaying && (
        <button className="replay-button" disabled={busy} onClick={goLive}>
          ● Back to live
        </button>
      )}

      {replaying && progress && (
        <div className="replay-progress">
          <div className="replay-progress-track">
            <div className="replay-progress-fill" style={{ width: `${percent}%` }} />
          </div>
          <span>
            {progress.finished
              ? "Replay finished"
              : `${formatDuration(progress.position_seconds)} / ${formatDuration(progress.duration_seconds)}`}
          </span>
        </div>
      )}

      {error && <div className="replay-error">{error}</div>}
    </div>
  );
}
