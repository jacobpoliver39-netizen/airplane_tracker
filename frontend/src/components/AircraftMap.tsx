
import { MapContainer, Marker, Popup, TileLayer } from "react-leaflet";
import L from "leaflet";
import type { Aircraft } from "../types/aircraft";
import "leaflet/dist/leaflet.css";

interface AircraftMapProps {
  aircraft: Aircraft[];
  selectedAircraftId: string | null;
  onSelectAircraft: (id: string) => void;
}

function createAircraftIcon(heading: number, selected: boolean) {
  return L.divIcon({
    className: "aircraft-marker",
    html: `<div class="aircraft-marker__symbol ${
      selected ? "aircraft-marker__symbol--selected" : ""
    }" style="transform: rotate(${heading}deg)">✈</div>`,
    iconSize: [32, 32],
    iconAnchor: [16, 16],
  });
}

export default function AircraftMap({
  aircraft,
  selectedAircraftId,
  onSelectAircraft,
}: AircraftMapProps) {
  return (
    <MapContainer
      center={[40.7, 22.95]}
      zoom={9}
      style={{
        height: "min(68vh, 760px)",
        minHeight: "480px",
        width: "100%",
      }}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />

      {aircraft.map((plane) => {
        const selected = plane.id === selectedAircraftId;

        return (
          <Marker
            key={plane.id}
            position={[plane.latitude, plane.longitude]}
            icon={createAircraftIcon(plane.heading, selected)}
            eventHandlers={{
              click: () => onSelectAircraft(plane.id),
            }}
          >
            <Popup>
              <strong>{plane.callsign}</strong>
              <br />
              Altitude: {plane.altitude.toLocaleString()} ft
              <br />
              Speed: {plane.speed} knots
              <br />
              Heading: {plane.heading}°
              <br />
              Distance: {plane.distance.toFixed(1)} nm
            </Popup>
          </Marker>
        );
      })}
    </MapContainer>
  );
}
