import { useState } from "react";
import type { TrackerEvent } from "../types/observers";

type EventFilter = "all" | "geofence" | "approach";

const FILTERS: { value: EventFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "geofence", label: "Geofence" },
  { value: "approach", label: "Approach" },
];

interface EventFeedProps {
  events: TrackerEvent[];
  // Callsigns currently tracked; events for other aircraft can't be selected.
  trackedIds: Set<string>;
  selectedAircraftId: string | null;
  onSelectAircraft: (id: string) => void;
}

function matchesFilter(event: TrackerEvent, filter: EventFilter): boolean {
  if (filter === "all") return true;
  if (filter === "approach") return event.type === "closest_approach";
  return event.type === "geofence_enter" || event.type === "geofence_exit";
}

function formatTime(seconds: number): string {
  return new Date(seconds * 1000).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function describe(event: TrackerEvent): { icon: string; text: string } {
  switch (event.type) {
    case "geofence_enter":
      return { icon: "⊕", text: `entered ${event.geofence ?? "geofence"}` };
    case "geofence_exit":
      return {
        icon: "⊖",
        text:
          `left ${event.geofence ?? "geofence"}` +
          (event.reason ? ` (${event.reason.replace("_", " ")})` : ""),
      };
    case "closest_approach":
      return { icon: "◎", text: "closest approach" };
    default:
      return { icon: "•", text: event.type };
  }
}

export default function EventFeed({
  events,
  trackedIds,
  selectedAircraftId,
  onSelectAircraft,
}: EventFeedProps) {
  const [filter, setFilter] = useState<EventFilter>("all");
  const visible = events.filter((event) => matchesFilter(event, filter));

  return (
    <section className="insight-panel">
      <div className="insight-heading">
        <div>
          <p className="eyebrow">EVENTS</p>
          <h3>Geofence and approach alerts</h3>
        </div>

        <div className="event-filters" role="group" aria-label="Event type">
          {FILTERS.map((option) => (
            <button
              key={option.value}
              className={`event-filter${filter === option.value ? " event-filter--active" : ""}`}
              aria-pressed={filter === option.value}
              onClick={() => setFilter(option.value)}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      {visible.length === 0 ? (
        <p className="insight-empty">
          {events.length === 0
            ? "No events yet. Aircraft entering or leaving a geofence, or passing their closest point to you, appear here."
            : "No events of this type yet."}
        </p>
      ) : (
        <ol className="event-list">
          {visible.map((event) => {
            const { icon, text } = describe(event);
            const tracked = trackedIds.has(event.callsign);
            const selected = event.callsign === selectedAircraftId;

            return (
              <li key={event.id}>
                <button
                  className={`event-row event-row--${event.type}${selected ? " event-row--selected" : ""}`}
                  disabled={!tracked}
                  title={tracked ? "Show on map" : "No longer tracked"}
                  onClick={() => onSelectAircraft(event.callsign)}
                >
                  <span className="event-time">{formatTime(event.time)}</span>
                  <span className="event-icon" aria-hidden="true">
                    {icon}
                  </span>
                  <span className="event-callsign">{event.callsign}</span>
                  <span className="event-text">{text}</span>
                  <span className="event-distance">
                    {event.distance_miles.toFixed(2)} mi
                  </span>
                </button>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
