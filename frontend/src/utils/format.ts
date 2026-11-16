// Display helpers. Each accepts null/undefined/NaN and shows a dash, so
// one missing field from the API cannot crash a render.

const MISSING = "—";

function isFiniteNumber(value: number | null | undefined): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

export function formatNumber(
  value: number | null | undefined,
  digits: number,
  unit: string,
): string {
  if (!isFiniteNumber(value)) {
    return MISSING;
  }

  // Degrees attach directly to the number (40.6°); other units get a space.
  const separator = unit === "°" ? "" : " ";
  return `${value.toFixed(digits)}${separator}${unit}`;
}

export function formatAltitude(value: number | null | undefined): string {
  return isFiniteNumber(value)
    ? `${Math.round(value).toLocaleString()} ft`
    : MISSING;
}

export function formatSpeed(value: number | null | undefined): string {
  return isFiniteNumber(value) ? `${Math.round(value)} mph` : MISSING;
}

export function formatHeading(value: number | null | undefined): string {
  if (!isFiniteNumber(value)) {
    return MISSING;
  }

  return `${(Math.round(value) % 360).toString().padStart(3, "0")}°`;
}

export function formatApproachTime(
  seconds: number | null | undefined,
  emptyLabel = "No future approach",
): string {
  if (!isFiniteNumber(seconds) || seconds < 0) {
    return emptyLabel;
  }

  const totalSeconds = Math.round(seconds);
  const minutes = Math.floor(totalSeconds / 60);
  const remainingSeconds = totalSeconds % 60;

  if (minutes === 0) {
    return `${remainingSeconds}s`;
  }

  return `${minutes}m ${remainingSeconds.toString().padStart(2, "0")}s`;
}
