import { useEffect, useRef } from "react";
import { useMap } from "react-leaflet";
import L from "leaflet";
import type { Aircraft, LatLng } from "../types/aircraft";
import {
  angleDifference,
  sampleTrack,
  travel,
  type Track,
} from "../animation/motion";
import {
  formatAltitude,
  formatHeading,
  formatNumber,
  formatSpeed,
} from "../utils/format";

// How long a plane takes to glide from its old predicted path onto the
// path from a new position fix.
const CORRECTION_MS = 1500;

// A correction bigger than this is a different flight or bad data:
// jump straight to the new position instead of gliding across the map.
const MAX_GLIDE_DEGREES = 0.1; // about 7 miles

// The ✈ glyph points east, so rotate by heading - 90.
const ICON_ROTATION_OFFSET = -90;

interface Correction {
  latitude: number;
  longitude: number;
  heading: number;
  startedAt: number; // ms
}

interface Entry {
  plane: Aircraft;
  track: Track;
  turning: boolean; // following the curved prediction
  correction: Correction | null;
  marker: L.Marker;
  straightLine: L.Polyline;
  curvedLine: L.Polyline;
  renderedRotation: number | null;
}

interface Frame {
  position: LatLng;
  heading: number;
  curvedPath: LatLng[];
  straightPath: LatLng[];
}

interface AircraftLayerProps {
  aircraft: Aircraft[];
  selectedAircraftId: string | null;
  onSelectAircraft: (id: string) => void;
}

function buildTrack(plane: Aircraft): { track: Track; turning: boolean } {
  const curved = plane.curved_trajectory;
  const points =
    curved && curved.length > 1
      ? curved
      : plane.straight_trajectory && plane.straight_trajectory.length > 1
        ? plane.straight_trajectory
        : [[plane.latitude, plane.longitude] as LatLng];

  return {
    track: {
      startTime: plane.timestamp,
      stepSeconds: plane.trajectory_step_seconds,
      points,
    },
    turning: points === curved,
  };
}

function escapeHtml(text: string): string {
  return text.replace(/[&<>"']/g, (character) => `&#${character.charCodeAt(0)};`);
}

function popupHtml(plane: Aircraft): string {
  return `
    <strong>${escapeHtml(plane.callsign)}</strong><br />
    Altitude: ${formatAltitude(plane.altitude)}<br />
    Speed: ${formatSpeed(plane.speed)}<br />
    Heading: ${formatHeading(plane.heading)}<br />
    Distance: ${formatNumber(plane.distance, 1, "miles")}
  `;
}

function createIcon(selected: boolean): L.DivIcon {
  return L.divIcon({
    className: "aircraft-marker",
    html: `<div class="aircraft-marker__symbol ${
      selected ? "aircraft-marker__symbol--selected" : ""
    }">✈</div>`,
    iconSize: [32, 32],
    iconAnchor: [16, 16],
  });
}

function straightStyle(selected: boolean): L.PolylineOptions {
  return {
    color: selected ? "#fbbf24" : "#60a5fa",
    weight: selected ? 3 : 2,
    opacity: 0.8,
    dashArray: "3 7",
    lineCap: "round",
    interactive: false,
  };
}

function curvedStyle(selected: boolean): L.PolylineOptions {
  return {
    color: selected ? "#a78bfa" : "#34d399",
    weight: selected ? 4 : 2.5,
    opacity: 0.9,
    lineCap: "round",
    interactive: false,
  };
}

/** Smoothstep: eases a correction in and out instead of moving linearly. */
function remainingCorrection(correction: Correction, nowMs: number): number {
  const progress = Math.min((nowMs - correction.startedAt) / CORRECTION_MS, 1);
  const eased = progress * progress * (3 - 2 * progress);
  return 1 - eased;
}

/** Where to draw an aircraft at nowMs, including any correction glide. */
function computeFrame(entry: Entry, nowMs: number): Frame {
  const sample = sampleTrack(entry.track, nowMs / 1000);
  let heading = sample.heading ?? entry.plane.heading;
  let path = sample.remainingPath;

  if (entry.correction) {
    const weight = remainingCorrection(entry.correction, nowMs);

    if (weight <= 0) {
      entry.correction = null;
    } else {
      const { latitude, longitude } = entry.correction;
      path = path.map(([lat, lon]) => [
        lat + latitude * weight,
        lon + longitude * weight,
      ]);
      heading += entry.correction.heading * weight;
    }
  }

  const position = path[0];

  // On a straight track the dashed line is the track itself. On a curved
  // one it is the tangent: where the aircraft would go if it stopped
  // turning now, over the same remaining time.
  const straightPath = entry.turning
    ? [
        position,
        travel(
          position,
          heading,
          (entry.plane.speed * sample.remainingSeconds) / 3600,
        ),
      ]
    : path;

  return {
    position,
    heading,
    curvedPath: entry.turning ? path : [],
    straightPath,
  };
}

function applyFrame(entry: Entry, frame: Frame) {
  entry.marker.setLatLng(frame.position);
  entry.curvedLine.setLatLngs(frame.curvedPath);
  entry.straightLine.setLatLngs(frame.straightPath);

  // Rotating the icon is a style write; skip it when nothing changed.
  const rotation =
    Math.round((frame.heading + ICON_ROTATION_OFFSET) * 10) / 10;
  const symbol = entry.marker.getElement()?.firstElementChild;

  if (symbol instanceof HTMLElement && rotation !== entry.renderedRotation) {
    symbol.style.transform = `rotate(${rotation}deg)`;
    entry.renderedRotation = rotation;
  }
}

function restyle(entry: Entry, selected: boolean) {
  entry.marker.setIcon(createIcon(selected));
  entry.marker.setZIndexOffset(selected ? 1000 : 0);
  entry.straightLine.setStyle(straightStyle(selected));
  entry.curvedLine.setStyle(curvedStyle(selected));
  entry.renderedRotation = null; // setIcon replaced the element
}

/**
 * Draws aircraft and their predicted paths, moving each plane along its
 * prediction every animation frame so it appears live between polls.
 * Leaflet layers are updated directly rather than re-rendered by React.
 */
export default function AircraftLayer({
  aircraft,
  selectedAircraftId,
  onSelectAircraft,
}: AircraftLayerProps) {
  const map = useMap();
  const entriesRef = useRef(new Map<string, Entry>());
  const selectedRef = useRef(selectedAircraftId);
  const onSelectRef = useRef(onSelectAircraft);

  useEffect(() => {
    onSelectRef.current = onSelectAircraft;
  }, [onSelectAircraft]);

  // Remove every layer when the map goes away.
  useEffect(() => {
    const entries = entriesRef.current;

    return () => {
      for (const entry of entries.values()) {
        entry.marker.remove();
        entry.straightLine.remove();
        entry.curvedLine.remove();
      }
      entries.clear();
    };
  }, [map]);

  // Sync layers with the latest API data.
  useEffect(() => {
    const entries = entriesRef.current;
    const nowMs = Date.now();
    const seen = new Set<string>();

    for (const plane of aircraft) {
      seen.add(plane.id);
      const existing = entries.get(plane.id);
      const selected = plane.id === selectedRef.current;

      if (!existing) {
        const { track, turning } = buildTrack(plane);
        const marker = L.marker([plane.latitude, plane.longitude], {
          icon: createIcon(selected),
          zIndexOffset: selected ? 1000 : 0,
        })
          .bindPopup(popupHtml(plane))
          .on("click", () => onSelectRef.current(plane.id));

        const entry: Entry = {
          plane,
          track,
          turning,
          correction: null,
          marker,
          straightLine: L.polyline([], straightStyle(selected)),
          curvedLine: L.polyline([], curvedStyle(selected)),
          renderedRotation: null,
        };

        entry.straightLine.addTo(map);
        entry.curvedLine.addTo(map);
        marker.addTo(map);
        applyFrame(entry, computeFrame(entry, nowMs));
        entries.set(plane.id, entry);
        continue;
      }

      // The API is polled more often than OpenSky updates, so most
      // responses repeat the same fix; only a new position time moves
      // the plane onto a new path.
      if (plane.timestamp !== existing.plane.timestamp) {
        // Glide from where the plane is drawn now onto the new path.
        const before = computeFrame(existing, nowMs);
        const { track, turning } = buildTrack(plane);
        existing.plane = plane;
        existing.track = track;
        existing.turning = turning;
        existing.correction = null;

        const after = computeFrame(existing, nowMs);
        const latitude = before.position[0] - after.position[0];
        const longitude = before.position[1] - after.position[1];

        if (Math.hypot(latitude, longitude) < MAX_GLIDE_DEGREES) {
          existing.correction = {
            latitude,
            longitude,
            heading: angleDifference(before.heading, after.heading),
            startedAt: nowMs,
          };
        }
      } else {
        existing.plane = plane;
      }

      existing.marker.setPopupContent(popupHtml(plane));
    }

    for (const [id, entry] of entries) {
      if (!seen.has(id)) {
        entry.marker.remove();
        entry.straightLine.remove();
        entry.curvedLine.remove();
        entries.delete(id);
      }
    }
  }, [aircraft, map]);

  // Restyle when the selection changes.
  useEffect(() => {
    selectedRef.current = selectedAircraftId;

    for (const [id, entry] of entriesRef.current) {
      restyle(entry, id === selectedAircraftId);
    }
  }, [selectedAircraftId]);

  // Animation loop. Browsers pause requestAnimationFrame in hidden tabs.
  useEffect(() => {
    let frameId = 0;

    const tick = () => {
      const nowMs = Date.now();

      for (const entry of entriesRef.current.values()) {
        applyFrame(entry, computeFrame(entry, nowMs));
      }

      frameId = requestAnimationFrame(tick);
    };

    frameId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frameId);
  }, []);

  return null;
}
