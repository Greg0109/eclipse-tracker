import { useCallback, useEffect, useState } from "react";
import { getNextEclipse, getRecommendations, searchAddress } from "./api/client";
import { Controls } from "./components/Controls";
import { DayPlanner } from "./components/DayPlanner";
import { LocationPanel } from "./components/LocationPanel";
import { MapView } from "./components/MapView";
import type { Candidate, Eclipse } from "./types/api";

const DEFAULT_LAT = 41.9;
const DEFAULT_LON = -4.2;
const DEFAULT_RANGE_KM = 100;

function App() {
  const [eclipse, setEclipse] = useState<Eclipse | null>(null);
  const [lat, setLat] = useState(DEFAULT_LAT);
  const [lon, setLon] = useState(DEFAULT_LON);
  const [rangeKm, setRangeKm] = useState(DEFAULT_RANGE_KM);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [selectedCandidate, setSelectedCandidate] = useState<Candidate | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [resolvedPlace, setResolvedPlace] = useState<string | null>(null);
  const [hasSearched, setHasSearched] = useState(false);

  useEffect(() => {
    getNextEclipse()
      .then(setEclipse)
      .catch((err: Error) => setError(err.message));
  }, []);

  // Nothing here runs on mount, on typing, or on moving the range slider. A recommendation search
  // costs tens of seconds against public APIs, so it happens only when the user asks for it.
  const runSearch = useCallback(
    async (query: string) => {
      if (loading) return;
      setLoading(true);
      setError(null);
      setWarnings([]);

      let searchLat = lat;
      let searchLon = lon;

      try {
        const trimmed = query.trim();
        if (trimmed) {
          const places = await searchAddress(trimmed);
          if (places.length === 0) {
            setError(`No places found for "${trimmed}".`);
            return;
          }
          searchLat = Number(places[0].lat);
          searchLon = Number(places[0].lon);
          setLat(searchLat);
          setLon(searchLon);
          setResolvedPlace(places[0].display_name);
        }

        const response = await getRecommendations({
          lat: searchLat,
          lon: searchLon,
          range_km: rangeKm,
          limit: 20,
        });
        setCandidates(response.candidates);
        setWarnings(response.warnings ?? []);
        setSelectedCandidate(response.candidates[0] ?? null);
        setHasSearched(true);
      } catch (err) {
        setError((err as Error).message);
      } finally {
        setLoading(false);
      }
    },
    [lat, lon, rangeKm, loading],
  );

  // Only moves the origin - the user still has to press Search.
  const handleLocationChange = useCallback((newLat: number, newLon: number) => {
    setLat(newLat);
    setLon(newLon);
    setResolvedPlace(null);
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
        <div className="pointer-events-auto max-h-full overflow-y-auto">
          <Controls
            lat={lat}
            lon={lon}
            rangeKm={rangeKm}
            searching={loading}
            resolvedPlace={resolvedPlace}
            onRangeChange={setRangeKm}
            onLocationChange={handleLocationChange}
            onSearch={runSearch}
          />
        </div>

        {/* mr-12 keeps this column clear of MapLibre's zoom/compass control, which the map renders
            in its own top-right corner underneath these panels. */}
        <div className="pointer-events-auto mr-12 flex max-h-full flex-col items-end gap-4 overflow-y-auto">
          <LocationPanel candidate={selectedCandidate} />
          <DayPlanner candidate={selectedCandidate} eclipseId={eclipse?.id ?? null} />
        </div>
      </div>

      <div className="absolute bottom-4 left-4 z-10 max-w-sm space-y-2">
        {!loading && !hasSearched && !error && (
          <div className="glass-panel rounded-full px-4 py-2 text-xs text-astro-muted">
            Set a location, then press Search to find viewing spots.
          </div>
        )}
        {loading && (
          <div className="glass-panel rounded-full px-4 py-2 text-xs text-astro-muted">
            Searching... this can take a while - it queries the public OpenStreetMap API.
          </div>
        )}
        {hasSearched && !loading && candidates.length === 0 && !error && warnings.length === 0 && (
          <div className="glass-panel rounded-full px-4 py-2 text-xs text-astro-muted">
            No spots inside the totality path within {rangeKm} km. Try a larger radius.
          </div>
        )}
          {error && <div className="glass-panel rounded-full px-4 py-2 text-xs text-amber-300">{error}</div>}
        {warnings.map((warning) => (
          <div key={warning} className="glass-panel rounded-2xl px-4 py-2 text-xs text-amber-300">
            {warning}
          </div>
        ))}
      </div>
    </div>
  );
}

export default App;
