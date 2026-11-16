
import type { Aircraft } from "../types/aircraft";
import {
  formatAltitude,
  formatApproachTime,
  formatHeading,
  formatNumber,
  formatSpeed,
} from "../utils/format";

const NO_APPROACH = "No future approach predicted";

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
            <strong>{formatAltitude(aircraft.altitude)}</strong>
          </div>

          <div className="detail-item">
            <span>GROUND SPEED</span>
            <strong>{formatSpeed(aircraft.speed)}</strong>
          </div>

          <div className="detail-item">
            <span>HEADING</span>
            <strong>{formatHeading(aircraft.heading)}</strong>
          </div>

          <div className="detail-item">
            <span>CURRENT DISTANCE</span>
            <strong>{formatNumber(aircraft.distance, 1, "mi")}</strong>
          </div>
        </div>
      </div>

      <div className="details-section approach-section">
        <h4>PREDICTED CLOSEST APPROACH</h4>

        <div className="detail-grid">
          <div className="detail-item">
            <span>CLOSEST DISTANCE</span>
            <strong>{formatNumber(aircraft.nearest_distance, 1, "mi")}</strong>
          </div>

          <div className="detail-item">
            <span>TIME TO CLOSEST POINT</span>
            <strong>
              {formatApproachTime(aircraft.nearest_distance_time, NO_APPROACH)}
            </strong>
          </div>
        </div>

        <p className="approach-note">
          Estimate assumes the aircraft maintains its current heading and speed.
        </p>

        {aircraft.curved_nearest_distance !== null &&
          aircraft.curved_nearest_distance_time !== null && (
            <div className="curved-approach">
              <h4>TURNING-FLIGHT ESTIMATE</h4>

              <div className="detail-grid">
                <div className="detail-item">
                  <span>CLOSEST DISTANCE</span>
                  <strong>
                    {formatNumber(aircraft.curved_nearest_distance, 1, "mi")}
                  </strong>
                </div>

                <div className="detail-item">
                  <span>TIME TO CLOSEST POINT</span>
                  <strong>
                    {formatApproachTime(
                      aircraft.curved_nearest_distance_time,
                      NO_APPROACH,
                    )}
                  </strong>
                </div>
              </div>

              <p className="approach-note">
                Estimate accounts for the aircraft's recent ground-track
                direction and turn rate.
              </p>
            </div>
          )}
      </div>

      <div className="details-section">
        <h4>POSITION</h4>

        <div className="coordinate-row">
          <span>Latitude</span>
          <strong>{formatNumber(aircraft.latitude, 5, "°")}</strong>
        </div>

        <div className="coordinate-row">
          <span>Longitude</span>
          <strong>{formatNumber(aircraft.longitude, 5, "°")}</strong>
        </div>
      </div>

      <div className="details-footer">
        <span className="status-dot" />
        <span>LIVE TRACKING DATA</span>
      </div>
    </aside>
  );
}
