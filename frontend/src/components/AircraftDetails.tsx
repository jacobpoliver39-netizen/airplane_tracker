
import type { Aircraft } from "../types/aircraft";

interface AircraftDetailsProps {
  aircraft: Aircraft | null;
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
            <strong>{aircraft.speed} kt</strong>
          </div>

          <div className="detail-item">
            <span>HEADING</span>
            <strong>
              {aircraft.heading.toString().padStart(3, "0")}°
            </strong>
          </div>

          <div className="detail-item">
            <span>DISTANCE</span>
            <strong>{aircraft.distance.toFixed(1)} nm</strong>
          </div>
        </div>
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
        <span>SIMULATED POSITION DATA</span>
      </div>
    </aside>
  );
}
