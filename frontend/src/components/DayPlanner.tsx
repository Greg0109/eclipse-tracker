import { useEffect, useState } from "react";
import { getItinerary } from "../api/client";
import type { Candidate, ItineraryResponse } from "../types/api";

interface DayPlannerProps {
  candidate: Candidate | null;
  eclipseId: string | null;
}

export function DayPlanner({ candidate, eclipseId }: DayPlannerProps) {
  const [itinerary, setItinerary] = useState<ItineraryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!candidate || !eclipseId) {
      setItinerary(null);
      return undefined;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    // Drop the previous candidate's plan immediately - itinerary lookups hit a slow public API,
    // and showing a stale timeline next to a new selection reads as "it didn't update".
    setItinerary(null);
    getItinerary({
      candidate_id: candidate.id,
      candidate_name: candidate.name,
      eclipse_id: eclipseId,
      lat: candidate.lat,
      lon: candidate.lon,
    })
      .then((response) => {
        if (!cancelled) setItinerary(response);
      })
      .catch((err: Error) => {
        // No backend is an expected state for the static build; App already explains it once.
        if (!cancelled && err.name !== "ApiNotConfiguredError") setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [candidate, eclipseId]);

  if (!candidate) return null;

  return (
    <div className="glass-panel w-80 space-y-3 rounded-2xl p-4">
      <h2 className="text-sm font-semibold text-astro-text">Day plan</h2>
      {loading && <p className="text-xs text-astro-muted">Building itinerary...</p>}
      {error && <p className="text-xs text-amber-300">{error}</p>}
      {itinerary && (
        <ol className="relative space-y-4 border-l border-astro-border pl-4">
          {itinerary.stops.map((stop, index) => (
            <li key={`${stop.kind}-${index}`} className="relative">
              <span className="absolute top-1 -left-[21px] h-2.5 w-2.5 rounded-full bg-astro-accent" />
              <p className="text-xs text-astro-muted">{stop.start_local_hint}</p>
              <p className="text-sm font-medium text-astro-text capitalize">
                {stop.kind}: {stop.name}
              </p>
              <p className="text-xs text-astro-muted">{stop.note}</p>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
