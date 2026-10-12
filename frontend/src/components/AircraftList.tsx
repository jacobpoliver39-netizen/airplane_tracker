
import type { Aircraft } from "../types/aircraft";

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
          </button>
        ))}
      </div>
    </aside>
  );
}
