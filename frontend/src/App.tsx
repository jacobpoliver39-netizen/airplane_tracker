
import { useEffect, useState } from "react";
import AircraftMap from "./components/AircraftMap";
import AircraftList from "./components/AircraftList";
import type { Aircraft } from "./types/aircraft";
import "./App.css";
import AircraftDetails from "./components/AircraftDetails";

function App() {
  const [selectedAircraftId, setSelectedAircraftId] = useState<string | null>(
    null
  );
  const [searchQuery, setSearchQuery] = useState("");
  const [distanceFilter, setDistanceFilter] = useState("all");
  const [altitudeFilter, setAltitudeFilter] = useState("all");
  const [aircraft, setAircraft] = useState<Aircraft[]>([]);
  
  useEffect(() => {
  let isMounted = true;

  const fetchAircraft = async () => {
    try {
      const response = await fetch(
        "http://127.0.0.1:8000/aircraft"
      );

      if (!response.ok) {
        throw new Error(`API request failed: ${response.status}`);
      }

      const data: Aircraft[] = await response.json();

      if (isMounted) {
        setAircraft(data);
      }
    } catch (error) {
      console.error("Failed to fetch aircraft:", error);
    }
  };

  fetchAircraft();

  const intervalId = setInterval(fetchAircraft, 5000);

  return () => {
    isMounted = false;
    clearInterval(intervalId);
  };
}, []);

  const filteredAircraft = aircraft.filter((plane) => {
    
    const matchesSearch = plane.callsign
      .toLowerCase()
      .includes(searchQuery.trim().toLowerCase());

    const matchesDistance =
      distanceFilter === "all" ||
      plane.distance <= Number(distanceFilter);

    const matchesAltitude =
      altitudeFilter === "all" ||
      (altitudeFilter === "low" && plane.altitude < 10000) ||
      (altitudeFilter === "medium" &&
        plane.altitude >= 10000 &&
        plane.altitude <= 25000) ||
      (altitudeFilter === "high" && plane.altitude > 25000);

    return matchesSearch && matchesDistance && matchesAltitude;
  });

    const selectedAircraft =
    filteredAircraft.find((plane) => plane.id === selectedAircraftId) ?? null;

  return (
    <main className="dashboard">
      <header className="topbar">
        <div className="brand">
          <div className="brand-icon">✈</div>
          <div>
            <h1>FlightScope</h1>
            <p>Aircraft surveillance</p>
          </div>
        </div>

        <div className="system-status">
          <span className="status-dot" />
          MOCK DATA
        </div>
      </header>

      <section className="overview">
        <div>
          <p className="eyebrow">AIRSPACE MONITOR</p>
          <h2>Thessaloniki Region</h2>
          <p className="subtitle">
            Aircraft activity and positional overview
          </p>
        </div>

        <div className="metric">
          <span className="metric-label">AIRCRAFT MATCHING FILTERS</span>
          <strong>
            {filteredAircraft.length.toString().padStart(2, "0")}
          </strong>
        </div>
      </section>

      <section className="map-section">
        <div className="section-heading">
          <h3>Air traffic overview</h3>
          <span>THESSALONIKI · GREECE</span>
        </div>

        <div className="filter-bar">
          <div className="search-control">
            <label htmlFor="aircraft-search">CALLSIGN</label>
            <input
              id="aircraft-search"
              type="search"
              placeholder="Search aircraft..."
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
            />
          </div>

          <div className="filter-control">
            <label htmlFor="distance-filter">MAX DISTANCE</label>
            <select
              id="distance-filter"
              value={distanceFilter}
              onChange={(event) => setDistanceFilter(event.target.value)}
            >
              <option value="all">Any distance</option>
              <option value="10">10 miles</option>
              <option value="25">25 miles</option>
              <option value="50">50 miles</option>
            </select>
          </div>

          <div className="filter-control">
            <label htmlFor="altitude-filter">ALTITUDE</label>
            <select
              id="altitude-filter"
              value={altitudeFilter}
              onChange={(event) => setAltitudeFilter(event.target.value)}
            >
              <option value="all">All altitudes</option>
              <option value="low">Below 10,000 ft</option>
              <option value="medium">10,000–25,000 ft</option>
              <option value="high">Above 25,000 ft</option>
            </select>
          </div>

          <button
            className="reset-filters"
            onClick={() => {
              setSearchQuery("");
              setDistanceFilter("all");
              setAltitudeFilter("all");
            }}
          >
            Reset
          </button>
        </div>

        <div className="results-summary">
          Showing {filteredAircraft.length} of {aircraft.length} aircraft
        </div>

        
<div className="surveillance-layout">
  <AircraftList
    aircraft={filteredAircraft}
    selectedAircraftId={selectedAircraftId}
    onSelectAircraft={setSelectedAircraftId}
  />

  <div className="map-container">
    <AircraftMap
      aircraft={filteredAircraft}
      selectedAircraftId={selectedAircraftId}
      onSelectAircraft={setSelectedAircraftId}
    />
  </div>
</div>

<AircraftDetails aircraft={selectedAircraft} />

      </section>

      <footer className="footer">
        <span>FLIGHTSCOPE / PERSONAL AVIATION PROJECT</span>
        <span>DATA: SIMULATED</span>
      </footer>
    </main>
  );
}

export default App;
