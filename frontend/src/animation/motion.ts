// Pure helpers for animating aircraft along their predicted paths.
// The server does the prediction; these only interpolate its points.

import type { LatLng } from "../types/aircraft";

/** A predicted path: points[i] is where the aircraft is at startTime + i * stepSeconds. */
export interface Track {
  startTime: number; // Unix seconds
  stepSeconds: number;
  points: LatLng[];
}

export interface TrackSample {
  position: LatLng;
  heading: number | null; // degrees, null when the aircraft is not moving
  remainingPath: LatLng[]; // from position to the end of the track
  remainingSeconds: number;
}

const MILES_PER_DEGREE_LATITUDE = 69.09;
const toRadians = (degrees: number) => (degrees * Math.PI) / 180;
const toDegrees = (radians: number) => (radians * 180) / Math.PI;

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

/** Signed shortest difference a - b in degrees, in [-180, 180). */
export function angleDifference(a: number, b: number): number {
  return ((((a - b + 180) % 360) + 360) % 360) - 180;
}

/** Initial compass bearing from one point to another, or null if they coincide. */
export function bearing(from: LatLng, to: LatLng): number | null {
  if (from[0] === to[0] && from[1] === to[1]) {
    return null;
  }

  const lat1 = toRadians(from[0]);
  const lat2 = toRadians(to[0]);
  const deltaLon = toRadians(to[1] - from[1]);

  const y = Math.sin(deltaLon) * Math.cos(lat2);
  const x =
    Math.cos(lat1) * Math.sin(lat2) -
    Math.sin(lat1) * Math.cos(lat2) * Math.cos(deltaLon);

  return (toDegrees(Math.atan2(y, x)) + 360) % 360;
}

/** Point reached by travelling distanceMiles on headingDegrees (short distances). */
export function travel(
  from: LatLng,
  headingDegrees: number,
  distanceMiles: number,
): LatLng {
  const heading = toRadians(headingDegrees);
  const north = distanceMiles * Math.cos(heading);
  const east = distanceMiles * Math.sin(heading);

  return [
    from[0] + north / MILES_PER_DEGREE_LATITUDE,
    from[1] +
      east / (MILES_PER_DEGREE_LATITUDE * Math.cos(toRadians(from[0]))),
  ];
}

/**
 * Where the aircraft is on its track at nowSeconds. Time before the track
 * starts or after it ends is clamped, so a stale track parks at its end.
 */
export function sampleTrack(track: Track, nowSeconds: number): TrackSample {
  const { points, stepSeconds } = track;

  if (points.length < 2 || stepSeconds <= 0) {
    return {
      position: points[0],
      heading: null,
      remainingPath: [points[0]],
      remainingSeconds: 0,
    };
  }

  const lastSegment = points.length - 2;
  const duration = (points.length - 1) * stepSeconds;
  const elapsed = clamp(nowSeconds - track.startTime, 0, duration);

  const index = Math.min(Math.floor(elapsed / stepSeconds), lastSegment);
  const fraction = elapsed / stepSeconds - index;
  const a = points[index];
  const b = points[index + 1];

  const position: LatLng = [
    a[0] + (b[0] - a[0]) * fraction,
    a[1] + (b[1] - a[1]) * fraction,
  ];

  return {
    position,
    heading: interpolatedHeading(points, elapsed / stepSeconds),
    remainingPath: [position, ...points.slice(index + 1)],
    remainingSeconds: duration - elapsed,
  };
}

/**
 * Heading at a fractional step along the track. Each segment's bearing is
 * the heading at its midpoint; blending neighbouring segments avoids the
 * icon snapping round every step on a curved track.
 */
function interpolatedHeading(points: LatLng[], step: number): number | null {
  const lastSegment = points.length - 2;
  const position = clamp(step - 0.5, 0, lastSegment);
  const index = Math.min(Math.floor(position), lastSegment);
  const fraction = position - index;

  const current = bearing(points[index], points[index + 1]);

  if (current === null || index === lastSegment) {
    return current;
  }

  const next = bearing(points[index + 1], points[index + 2]);

  if (next === null) {
    return current;
  }

  return (current + angleDifference(next, current) * fraction + 360) % 360;
}
