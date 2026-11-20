import { Circle, MapContainer, TileLayer, Tooltip } from "react-leaflet";
import type { Aircraft } from "../types/aircraft";
import type { Geofence } from "../types/observers";
import "leaflet/dist/leaflet.css";
import { USER_POSITION } from "../config";
import AircraftLayer from "./AircraftLayer";

const METERS_PER_MILE = 1609.344;

interface AircraftMapProps {
  aircraft: Aircraft[];
  geofences?: Geofence[];
  selectedAircraftId: string | null;
  onSelectAircraft: (id: string) => void;
}

export default function AircraftMap({
  aircraft,
  geofences = [],
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

      {geofences.map((fence) => (
        <Circle
          key={fence.name}
          center={[fence.latitude, fence.longitude]}
          radius={fence.radius_miles * METERS_PER_MILE}
          pathOptions={{
            color: "#f59e0b",
            weight: 1,
            opacity: 0.6,
            dashArray: "4 6",
            fillColor: "#f59e0b",
            fillOpacity: 0.05,
          }}
          interactive={true}
        >
          <Tooltip sticky>
            {fence.name} geofence · {fence.radius_miles} mi
          </Tooltip>
        </Circle>
      ))}

      <AircraftLayer
        aircraft={aircraft}
        selectedAircraftId={selectedAircraftId}
        onSelectAircraft={onSelectAircraft}
      />
    </MapContainer>
  );
}
