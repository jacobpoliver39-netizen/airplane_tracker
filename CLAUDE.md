# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

JacobSky: polls the OpenSky Network API for aircraft near Thessaloniki, Greece (user position = ACT Campus, lon 23.0 / lat 40.6), predicts their trajectories, and serves them to a React + Leaflet map dashboard. It is also a course project on OO design patterns. `docs/baseline.md` records the pre-refactor design and is the "before" side of that comparison, so don't rewrite it to match current code.

## Commands

Backend (Python 3.14, venv at `.venv`, deps in `requirements.txt`). Run everything from the repo root. The modules are flat top-level files imported by bare name (`from calculator import Calculator`), and there's no package or conftest.

```bash
.venv/bin/python -m pytest -q                                   # all tests
.venv/bin/python -m pytest tests/test_calculator.py -q          # one file
.venv/bin/python -m pytest tests/test_calculator.py::test_distance_to_same_coordinates_is_zero
.venv/bin/uvicorn api:app --reload                              # API on :8000; starts the polling thread
.venv/bin/python main.py                                        # polling loop only, no API
.venv/bin/python collect_opensky.py                             # append raw observations to data/opensky_observations.csv
.venv/bin/python record_opensky.py [--hours 6] [-o FILE]       # record raw responses to data/recordings/*.jsonl for replay
.venv/bin/python record_opensky.py --from-csv data/opensky_observations.csv   # turn the collector CSV into a recording
JACOBSKY_REPLAY=data/recordings/FILE.jsonl .venv/bin/uvicorn api:app   # replay a recording instead of polling OpenSky
```

Frontend (`frontend/`, Vite + React 19 + TypeScript):

```bash
npm run dev      # :5173 (only origin allowed by CORS in api.py)
npm run build    # tsc -b && vite build
npm run lint
```

The frontend reads the API URL from `VITE_API_URL` (default `http://127.0.0.1:8000`, see `frontend/src/config.ts`) and polls `/aircraft` every 5 s.

OpenSky access: set `OPENSKY_CLIENT_ID` / `OPENSKY_CLIENT_SECRET` (OAuth2 client credentials) for the 4000-credit daily quota; without them access is anonymous (400 credits/day). The poll interval defaults to 15 s anonymous / 30 s authenticated (`config.py`, override with `JACOBSKY_POLL_INTERVAL`). 15 s exceeds the anonymous quota after about 1.5 h; the poller then backs off on 429 until credits refill. The collector and the API each spend credits, so running both doubles usage.

## Architecture

Data flow: `api.py` lifespan → background thread running `main.main(stop_event)` → `OpenSkyClient` every `config.POLL_INTERVAL_SECONDS` → `Aircraft` objects in the shared `AircraftTracker` (`tracker_state.aircraft_tracker`, a module-level singleton) → `GET /aircraft` serializes `tracker.get_sorted_aircrafts()` → `frontend/src/App.tsx`.

- **`config.py`** holds user position, bounding box, poll interval, grace period and minimum altitude; `opensky_client.py` handles the request, OAuth token, response-shape validation and 429 (`OpenSkyRateLimitError` with the retry-after seconds).
- **`main.py`**: the client validates the response shape *before* the tracker is touched, so a failed or malformed request leaves it alone. `apply_states` uses `OpenSkyAdapter` (`opensky_adapter.py`, the only code that knows OpenSky's format) to turn states into provider-neutral `AircraftObservation`s (`observation.py`), and `AircraftFactory` (`aircraft_factory.py`) to build new `Aircraft`. `OpenSkyAdapter.parse_state` converts OpenSky's positional arrays (index 1 callsign, 3 time_position, 5 lon, 6 lat, 7 baro alt m, 8 on_ground, 9 velocity m/s, 10 heading) and skips individual states missing a callsign, position, time, velocity or heading. Callsigns are stripped and used as the tracker key. Aircraft on the ground or below `MINIMUM_ALTITUDE_FEET` are never added; a tracked aircraft that descends is updated and then removed once by `RemoveLowAltitudeAircraftCommand`. Missing aircraft are kept until their last position is older than `MISSING_AIRCRAFT_GRACE_SECONDS`. Each poll cycle is wrapped in a catch-all so the thread cannot die.
- **Threading**: `AircraftTracker.lock` (re-entrant) must be held for any multi-step read or change of the tracker or its `Aircraft` objects. `main.apply_states` and the `/aircraft` endpoint each hold it for their whole pass.
- **Units**: altitude is converted to **feet** and speed to **mph**, distances are **statute miles**, and turn rate is deg/s (positive = clockwise). A missing altitude is `None` (and the frontend shows a dash); velocity is passed through as reported. `Calculator.calculate_haversine_distance` is not rounded; round only for output (the API does).
- **`aircraft.py`**: `Aircraft` keeps `location_history` (timestamp → `Position`). When an update has a newer timestamp, it first snapshots and scores the previous prediction against the actual position (`prediction_errors`, capped at 500), then updates its state. The straight-line nearest-approach methods and the curved CTRV ones (`get_curved_nearest_approach`, `get_curved_trajectory`) both read this history; both predictions start from the **reported** speed and heading (OpenSky's current track); the history only supplies the turn rate for the curve. Don't start the curve from `get_estimated_ground_motion` (least-squares over past positions): during a turn it lags the real track by up to ~100°, which drew the curve out of the side of the plane. `get_approach_speed_towards_user` returns `None` without enough history. `nearest_approach_ctrv` returns `None` when the closest point is at either end of the 60 s window (moving away, or still closing).
- **`calculator.py`**: a stateless `Calculator` with only static methods. It has haversine/bearing math, a GPS ↔ local east/north (miles) projection, least-squares ground motion and turn-rate estimation from recent observations, and CTRV (constant turn rate and velocity) prediction and nearest approach.
- **Design patterns** (keep these intact when refactoring):
  - Strategy: `ranking_strategies.py` (`NearestStrategy` default, `FastestApproachStrategy`, `NearestPredictedApproachStrategy` — curved nearest approach, falling back to straight-line), injected into `AircraftTracker`. `GET /aircraft?rank=nearest|fastest|predicted` picks one per request from `RANKING_STRATEGIES` without changing the tracker's default; the frontend's "Sort by" dropdown sends it. Adding a strategy means updating the registry, the `Literal` on `api.get_aircraft` and `RankOption` in `App.tsx`.
  - Adapter / Factory Method: `OpenSkyAdapter` → `AircraftObservation` → `AircraftFactory.create`.
  - Command: `commands.py`. `RemoveMissingAircraftCommand` and `RemoveLowAltitudeAircraftCommand` are run by `main.py` after each poll.
  - Singleton: `logging_service.py`. Use `LoggingService.initialize()`, not the constructor. Logs go to `logs/jacobsky_YYYY-MM-DD.log` (INFO+, `DailyFileHandler` switches file at midnight) and stderr (WARNING+). Tests call `LoggingService.reset()` (`close()` is an alias).
- **API contract**: if you add or rename a field in `api.serialize_aircraft`, update `frontend/src/types/aircraft.ts` and `tests/test_api.py` as well. Both projections (`straight_trajectory`, `curved_trajectory`) are computed server-side and sampled every `trajectory_step_seconds` starting at the position time `timestamp`; the frontend only interpolates them.
- **Map animation** (`frontend/src/components/AircraftLayer.tsx`, `src/animation/motion.ts`): Leaflet layers are managed imperatively, not as React components. A `requestAnimationFrame` loop dead-reckons each plane along its curved (else straight) trajectory using `Date.now()` vs `timestamp`, and a new fix glides the plane onto its new path over 1.5 s. Path lines start from the animated position. The API tests use `FakeAircraft` stubs, so any new method the endpoint calls has to exist on the stub too.
- **Record / replay**: `flight_recording.py` defines the recording format (JSON Lines: a header, then one raw `/states/all` response per line, flushed per frame). `record_opensky.py` writes recordings. `replay_client.ReplayOpenSkyClient` is a drop-in for `OpenSkyClient` (same `get_states` / `seconds_until_next_poll` / `authenticated` / `close`); `main._create_client` picks it when `JACOBSKY_REPLAY` is set (`JACOBSKY_REPLAY_SPEED`, `_START` seconds, `_LOOP=1`). The replay shifts every timestamp by a constant offset so the session looks live, serves frames on the recorded schedule (gaps over 5 min are shortened), and returns no states after the end so the aircraft time out. The polling loop asks the client for the wait *after* each poll. Any fake client needs `seconds_until_next_poll`.
- `collect_opensky.py` is a standalone data collector, separate from the tracker (it shares `config.py` and `OpenSkyClient`). It writes the CSV under `data/` (gitignored) and is meant for offline comparison of predicted vs. actual tracks.

`to_do.txt` holds the author's running notes and open ideas. One example is animating planes between polls toward their predicted position.
