/**
 * The time the aircraft timestamps are on. Live, that is the wall clock;
 * in a sped-up replay it runs `speed` times faster. GET /source reports
 * the server's value, and between reports it is extrapolated locally so
 * the animation stays smooth.
 */

let anchorSimSeconds = Date.now() / 1000;
let anchorWallMs = Date.now();
let clockSpeed = 1;

export function simNowSeconds(): number {
  return anchorSimSeconds + ((Date.now() - anchorWallMs) / 1000) * clockSpeed;
}

export function simSpeed(): number {
  return clockSpeed;
}

/**
 * Align with the server's clock. Small differences (request latency) are
 * ignored, since re-anchoring on every poll would make planes jitter.
 */
export function syncSimClock(serverNowSeconds: number, speed: number) {
  const drift = Math.abs(simNowSeconds() - serverNowSeconds);

  if (speed !== clockSpeed || drift > Math.max(1, speed * 0.5)) {
    anchorSimSeconds = serverNowSeconds;
    anchorWallMs = Date.now();
    clockSpeed = speed;
  }
}
