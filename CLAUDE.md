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
```

Frontend (`frontend/`, Vite + React 19 + TypeScript):

```bash
npm run dev      # :5173 (only origin allowed by CORS in api.py)
npm run build    # tsc -b && vite build
npm run lint
```

The frontend hard-codes `http://127.0.0.1:8000/aircraft` and polls it every 5 s.

## Architecture

Data flow: `api.py` lifespan → background thread running `main.main(stop_event)` → OpenSky every 15 s → `Aircraft` objects in the shared `AircraftTracker` (`tracker_state.aircraft_tracker`, a module-level singleton) → `GET /aircraft` serializes `tracker.get_sorted_aircrafts()` → `frontend/src/App.tsx`.

- **`main.py`**: validates the OpenSky response *before* mutating the tracker. A failed or malformed request leaves the tracker alone; only a successful response may remove aircraft. It parses OpenSky's positional state arrays (index 1 callsign, 5 lon, 6 lat, 7 baro alt m, 9 velocity m/s, 10 heading…). Callsigns are stripped and used as the tracker key, and empty ones are skipped.
- **Units**: altitude is converted to **feet** and speed to **mph**, distances are **statute miles**, and turn rate is deg/s (positive = clockwise). A zero velocity is replaced by 1, and a missing altitude becomes 1.
- **`aircraft.py`**: `Aircraft` keeps `location_history` (timestamp → `Position`). When an update has a newer timestamp, it first snapshots and scores the previous prediction against the actual position (`prediction_errors`, capped at 500), then updates its state. The straight-line nearest-approach methods and the curved CTRV ones (`get_curved_nearest_approach`, `get_curved_trajectory`) both read this history.
- **`calculator.py`**: a stateless `Calculator` with only static methods. It has haversine/bearing math, a GPS ↔ local east/north (miles) projection, least-squares ground motion and turn-rate estimation from recent observations, and CTRV (constant turn rate and velocity) prediction and nearest approach.
- **Design patterns** (keep these intact when refactoring):
  - Strategy: `ranking_strategies.py` (`NearestStrategy` default, `FastestApproachStrategy`), injected into `AircraftTracker`.
  - Command: `commands.py`. `RemoveMissingAircraftCommand` and `RemoveLowAltitudeAircraftCommand` are run by `main.py` after each poll.
  - Singleton: `logging_service.py`. Use `LoggingService.initialize()`, not the constructor. Logs go to `logs/jacobsky_YYYY-MM-DD.log` (INFO+) and stderr (WARNING+). Tests call `LoggingService.reset()`.
- **API contract**: if you add or rename a field in the `/aircraft` dict in `api.py`, update `App.tsx` and `tests/test_api.py` as well. The API tests use `FakeAircraft` stubs, so any new method the endpoint calls has to exist on the stub too.
- `collect_opensky.py` is a standalone data collector, separate from the tracker. It writes the CSV under `data/` and is meant for offline comparison of predicted vs. actual tracks.

`to_do.txt` holds the author's running notes and open ideas. One example is animating planes between polls toward their predicted position.
