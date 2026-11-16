import { MapContainer, TileLayer } from "react-leaflet";
import type { Aircraft } from "../types/aircraft";
import "leaflet/dist/leaflet.css";
import { USER_POSITION } from "../config";
import AircraftLayer from "./AircraftLayer";

interface AircraftMapProps {
  aircraft: Aircraft[];
  selectedAircraftId: string | null;
  onSelectAircraft: (id: string) => void;
}

export default function AircraftMap({
  aircraft,
  selectedAircraftId,
  onSelectAircraft,
}: AircraftMapProps) {
  return (
    <MapContainer
      center={USER_POSITION}
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

      <AircraftLayer
        aircraft={aircraft}
        selectedAircraftId={selectedAircraftId}
        onSelectAircraft={onSelectAircraft}
      />
    </MapContainer>
  );
}
