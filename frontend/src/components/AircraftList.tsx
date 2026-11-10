
import type { Aircraft } from "../types/aircraft";

interface AircraftListProps {
  aircraft: Aircraft[];
  selectedAircraftId: string | null;
  onSelectAircraft: (id: string) => void;
}

function formatApproachTime(seconds: number | null): string {
  if (seconds === null || !Number.isFinite(seconds) || seconds < 0) {
    return "No future approach";
  }

  const totalSeconds = Math.round(seconds);
  const minutes = Math.floor(totalSeconds / 60);
  const remainingSeconds = totalSeconds % 60;

  if (minutes === 0) {
    return `${remainingSeconds}s`;
  }

  return `${minutes}m ${remainingSeconds.toString().padStart(2, "0")}s`;
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
              <span className="aircraft-callsign">{plane.callsign}</span>
              <span className="aircraft-heading">
                {plane.heading.toString().padStart(3, "0")}°
              </span>
            </div>

            <div className="aircraft-card-stats">
              <div>
                <span>ALTITUDE</span>
                <strong>{plane.altitude.toLocaleString()} ft</strong>
              </div>

              <div>
                <span>SPEED</span>
                <strong>{plane.speed} mph</strong>
              </div>

              <div>
                <span>DISTANCE</span>
                <strong>{plane.distance.toFixed(1)} mi</strong>
              </div>
            </div>

            <div className="aircraft-approach">
              <span className="approach-label">PREDICTED CLOSEST APPROACH</span>

              <div className="approach-stats">
                <div>
                  <span>Closest distance</span>
                  <strong>{plane.nearest_distance.toFixed(1)} mi</strong>
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
                        {plane.curved_nearest_distance.toFixed(1)} mi
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
