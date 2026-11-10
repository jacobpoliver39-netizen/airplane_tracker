
import type { Aircraft } from "../types/aircraft";

interface AircraftDetailsProps {
  aircraft: Aircraft | null;
}

function formatApproachTime(seconds: number | null): string {
  if (seconds === null || !Number.isFinite(seconds) || seconds < 0) {
    return "No future approach predicted";
  }

  const totalSeconds = Math.round(seconds);
  const minutes = Math.floor(totalSeconds / 60);
  const remainingSeconds = totalSeconds % 60;

  if (minutes === 0) {
    return `${remainingSeconds}s`;
  }

  return `${minutes}m ${remainingSeconds.toString().padStart(2, "0")}s`;
}

export default function AircraftDetails({
  aircraft,
}: AircraftDetailsProps) {
  if (!aircraft) {
    return (
      <aside className="details-panel details-empty">
        <div className="details-empty-icon">✈</div>
        <h3>No aircraft selected</h3>
        <p>
          Select an aircraft from the list or map to inspect its flight data.
        </p>
      </aside>
    );
  }

  return (
    <aside className="details-panel">
      <div className="details-header">
        <div>
          <p className="eyebrow">AIRCRAFT PROFILE</p>
          <h3>{aircraft.callsign}</h3>
        </div>

        <span className="details-status">TRACKED</span>
      </div>

      <div className="details-section">
        <h4>FLIGHT PARAMETERS</h4>

        <div className="detail-grid">
          <div className="detail-item">
            <span>ALTITUDE</span>
            <strong>{aircraft.altitude.toLocaleString()} ft</strong>
          </div>

          <div className="detail-item">
            <span>GROUND SPEED</span>
            <strong>{aircraft.speed} mph</strong>
          </div>

          <div className="detail-item">
            <span>HEADING</span>
            <strong>{aircraft.heading.toString().padStart(3, "0")}°</strong>
          </div>

          <div className="detail-item">
            <span>CURRENT DISTANCE</span>
            <strong>{aircraft.distance.toFixed(1)} mi</strong>
          </div>
        </div>
      </div>

      <div className="details-section approach-section">
        <h4>PREDICTED CLOSEST APPROACH</h4>

        <div className="detail-grid">
          <div className="detail-item">
            <span>CLOSEST DISTANCE</span>
            <strong>{aircraft.nearest_distance.toFixed(1)} mi</strong>
          </div>

          <div className="detail-item">
            <span>TIME TO CLOSEST POINT</span>
            <strong>
              {formatApproachTime(aircraft.nearest_distance_time)}
            </strong>
          </div>
        </div>

        <p className="approach-note">
          Estimate assumes the aircraft maintains its current heading and speed.
        </p>
      </div>

      <div className="details-section">
        <h4>POSITION</h4>

        <div className="coordinate-row">
          <span>Latitude</span>
          <strong>{aircraft.latitude.toFixed(5)}°</strong>
        </div>

        <div className="coordinate-row">
          <span>Longitude</span>
          <strong>{aircraft.longitude.toFixed(5)}°</strong>
        </div>
      </div>

      <div className="details-footer">
        <span className="status-dot" />
        <span>LIVE TRACKING DATA</span>
      </div>
    </aside>
  );
}
