
import {
  MapContainer,
  Marker,
  Popup,
  Polyline,
  TileLayer,
} from "react-leaflet";
import L from "leaflet";
import type { Aircraft } from "../types/aircraft";
import "leaflet/dist/leaflet.css";
import React from "react";

interface AircraftMapProps {
  aircraft: Aircraft[];
  selectedAircraftId: string | null;
  onSelectAircraft: (id: string) => void;
}

const PROJECTION_SECONDS = 60;
const EARTH_RADIUS_MILES = 3958.8;

function getProjectedPosition(plane: Aircraft): [number, number] {
  const distanceMiles =
    (plane.speed * PROJECTION_SECONDS) / 3600;

  const angularDistance = distanceMiles / EARTH_RADIUS_MILES;
  const headingRadians = (plane.heading * Math.PI) / 180;
  const latitudeRadians = (plane.latitude * Math.PI) / 180;
  const longitudeRadians = (plane.longitude * Math.PI) / 180;

  const projectedLatitude = Math.asin(
    Math.sin(latitudeRadians) * Math.cos(angularDistance) +
      Math.cos(latitudeRadians) *
        Math.sin(angularDistance) *
        Math.cos(headingRadians),
  );

  const projectedLongitude =
    longitudeRadians +
    Math.atan2(
      Math.sin(headingRadians) *
        Math.sin(angularDistance) *
        Math.cos(latitudeRadians),
      Math.cos(angularDistance) -
        Math.sin(latitudeRadians) * Math.sin(projectedLatitude),
    );

  return [
    (projectedLatitude * 180) / Math.PI,
    (projectedLongitude * 180) / Math.PI,
  ];
}

function createAircraftIcon(heading: number, selected: boolean) {
  return L.divIcon({
    className: "aircraft-marker",
    html: `<div class="aircraft-marker__symbol ${
      selected ? "aircraft-marker__symbol--selected" : ""
    }" style="transform: rotate(${heading - 90}deg)">✈</div>`,
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
        const projectedPosition = getProjectedPosition(plane);

        return (
          <React.Fragment key={plane.id}>
            <Polyline
              positions={[
                [plane.latitude, plane.longitude],
                projectedPosition,
              ]}
              pathOptions={{
                color: selected ? "#fbbf24" : "#60a5fa",
                weight: selected ? 3 : 2,
                opacity: 0.8,
                dashArray: "3 7",
                lineCap: "round",
              }}
              interactive={false}
            />

            <Marker
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
                Speed: {plane.speed} mph
                <br />
                Heading: {plane.heading}°
                <br />
                Projected track: {PROJECTION_SECONDS} seconds
                <br />
                Distance: {plane.distance.toFixed(1)} miles
              </Popup>
            </Marker>
          </React.Fragment>
        );
      })}
    </MapContainer>
  );
}
