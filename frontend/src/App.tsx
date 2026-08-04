import { useCallback, useEffect, useState } from "react";
import { getNextEclipse, getRecommendations } from "./api/client";
import { Controls } from "./components/Controls";
import { DayPlanner } from "./components/DayPlanner";
import { LocationPanel } from "./components/LocationPanel";
import { MapView } from "./components/MapView";
import type { Candidate, Eclipse } from "./types/api";

const DEFAULT_LAT = 41.9;
const DEFAULT_LON = -4.2;
const DEFAULT_RANGE_KM = 150;

function App() {
  const [eclipse, setEclipse] = useState<Eclipse | null>(null);
  const [lat, setLat] = useState(DEFAULT_LAT);
  const [lon, setLon] = useState(DEFAULT_LON);
  const [rangeKm, setRangeKm] = useState(DEFAULT_RANGE_KM);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [selectedCandidate, setSelectedCandidate] = useState<Candidate | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getNextEclipse()
      .then(setEclipse)
      .catch((err: Error) => setError(err.message));
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getRecommendations({ lat, lon, range_km: rangeKm, limit: 20 })
      .then((response) => {
        if (cancelled) return;
        setCandidates(response.candidates);
        setSelectedCandidate((current) => {
          if (current && response.candidates.some((candidate) => candidate.id === current.id)) return current;
          return response.candidates[0] ?? null;
        });
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [lat, lon, rangeKm]);

  const handleLocationChange = useCallback((newLat: number, newLon: number) => {
    setLat(newLat);
    setLon(newLon);
  }, []);

  return (
    <div className="relative h-full w-full overflow-hidden">
      <MapView
        eclipse={eclipse}
        candidates={candidates}
        selectedCandidateId={selectedCandidate?.id ?? null}
        onSelectCandidate={setSelectedCandidate}
      />

      <div className="pointer-events-none absolute inset-0 z-10 flex justify-between p-4">
        <div className="pointer-events-auto">
          <Controls lat={lat} lon={lon} rangeKm={rangeKm} onRangeChange={setRangeKm} onLocationChange={handleLocationChange} />
        </div>

        <div className="pointer-events-auto flex flex-col items-end gap-4">
          <LocationPanel candidate={selectedCandidate} />
          <DayPlanner candidate={selectedCandidate} eclipseId={eclipse?.id ?? null} />
        </div>
      </div>

      {(loading || error) && (
        <div className="absolute bottom-4 left-4 z-10">
          {loading && (
            <div className="glass-panel rounded-full px-4 py-2 text-xs text-astro-muted">Loading candidates...</div>
          )}
          {error && (
            <div className="glass-panel mt-2 rounded-full px-4 py-2 text-xs text-amber-300">{error}</div>
          )}
        </div>
      )}
    </div>
  );
}

export default App;
