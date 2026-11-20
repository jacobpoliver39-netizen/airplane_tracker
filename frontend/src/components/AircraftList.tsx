
import type { Aircraft } from "../types/aircraft";
import {
  formatAltitude,
  formatApproachTime,
  formatHeading,
  formatNumber,
  formatSpeed,
} from "../utils/format";

interface AircraftListProps {
  aircraft: Aircraft[];
  selectedAircraftId: string | null;
  onSelectAircraft: (id: string) => void;
}

export default function AircraftList({
  aircraft,
  selectedAircraftId,
  onSelectAircraft,
}: AircraftListProps) {
  return (
    <aside className="aircraft-panel">
      <div className="panel-heading">
        <div>
          <h3>Tracked aircraft</h3>
          <p>Select an aircraft to inspect it</p>
        </div>

        <span className="aircraft-count">{aircraft.length}</span>
      </div>

      <div className="aircraft-list">
        {aircraft.map((plane) => (
          <button
            key={plane.id}
            className={`aircraft-card ${
              selectedAircraftId === plane.id ? "selected" : ""
            }`}
            onClick={() => onSelectAircraft(plane.id)}
          >
            <div className="aircraft-card-top">
              <span className="aircraft-callsign">
                {plane.callsign}
                {plane.state === "missing" && (
                  <span className="state-tag" title="Not in the latest updates">
                    MISSING
                  </span>
                )}
              </span>
              <span className="aircraft-heading">
                {formatHeading(plane.heading)}
              </span>
            </div>

            <div className="aircraft-card-stats">
              <div>
                <span>ALTITUDE</span>
                <strong>{formatAltitude(plane.altitude)}</strong>
              </div>

              <div>
                <span>SPEED</span>
                <strong>{formatSpeed(plane.speed)}</strong>
              </div>

              <div>
                <span>DISTANCE</span>
                <strong>{formatNumber(plane.distance, 1, "mi")}</strong>
              </div>
            </div>

            <div className="aircraft-approach">
              <span className="approach-label">PREDICTED CLOSEST APPROACH</span>

              <div className="approach-stats">
                <div>
                  <span>Closest distance</span>
                  <strong>{formatNumber(plane.nearest_distance, 1, "mi")}</strong>
                </div>

                <div>
                  <span>Time to closest point</span>
                  <strong>
                    {formatApproachTime(plane.nearest_distance_time)}
                  </strong>
                </div>
              </div>
              {plane.curved_nearest_distance !== null &&
                plane.curved_nearest_distance_time !== null && (
                  <div className="approach-stats">
                    <div>
                      <span>Turning estimate</span>
                      <strong>
                        {formatNumber(plane.curved_nearest_distance, 1, "mi")}
                      </strong>
                    </div>

                    <div>
                      <span>Turning time to closest point</span>
                      <strong>
                        {formatApproachTime(
                          plane.curved_nearest_distance_time
                        )}
                      </strong>
                    </div>
                  </div>
                )}
            </div>
          </button>
        ))}
      </div>
    </aside>
  );
}
