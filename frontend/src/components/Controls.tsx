import { useEffect, useRef, useState } from "react";
import { searchAddress } from "../api/client";
import { useGeolocation } from "../hooks/useGeolocation";
import type { NominatimResult } from "../types/api";

interface ControlsProps {
  lat: number;
  lon: number;
  rangeKm: number;
  onRangeChange: (rangeKm: number) => void;
  onLocationChange: (lat: number, lon: number) => void;
}

const SEARCH_DEBOUNCE_MS = 1000;
const MIN_QUERY_LENGTH = 3;

export function Controls({ lat, lon, rangeKm, onRangeChange, onLocationChange }: ControlsProps) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<NominatimResult[]>([]);
  const [searching, setSearching] = useState(false);
  const debounceRef = useRef<number | undefined>(undefined);

  const {
    loading: locating,
    error: geoError,
    locate,
  } = useGeolocation((foundLat, foundLon) => onLocationChange(foundLat, foundLon));

  useEffect(() => {
    if (query.trim().length < MIN_QUERY_LENGTH) {
      setResults([]);
      return undefined;
    }
    window.clearTimeout(debounceRef.current);
    debounceRef.current = window.setTimeout(() => {
      setSearching(true);
      searchAddress(query)
        .then(setResults)
        .finally(() => setSearching(false));
    }, SEARCH_DEBOUNCE_MS);
    return () => window.clearTimeout(debounceRef.current);
  }, [query]);

  return (
    <div className="glass-panel w-80 space-y-4 rounded-2xl p-4">
      <div>
        <h1 className="text-base font-semibold text-astro-text">Eclipse Tracker</h1>
        <p className="text-xs text-astro-muted">Find the best spot to watch totality.</p>
      </div>

      <div className="space-y-1">
        <label className="text-xs text-astro-muted" htmlFor="address-search">
          Search a place
        </label>
        <input
          id="address-search"
          className="w-full rounded-lg border border-astro-border bg-white/5 px-3 py-2 text-sm text-astro-text placeholder:text-astro-muted focus:ring-1 focus:ring-astro-accent focus:outline-none"
          type="text"
          placeholder="City, address..."
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        {searching && <p className="text-xs text-astro-muted">Searching...</p>}
        {results.length > 0 && (
          <ul className="divide-y divide-white/5 overflow-hidden rounded-lg border border-astro-border">
            {results.map((result) => (
              <li key={`${result.lat},${result.lon}`}>
                <button
                  type="button"
                  className="w-full px-3 py-2 text-left text-xs hover:bg-white/10"
                  onClick={() => {
                    onLocationChange(Number(result.lat), Number(result.lon));
                    setQuery(result.display_name);
                    setResults([]);
                  }}
                >
                  {result.display_name}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <button
        type="button"
        onClick={locate}
        disabled={locating}
        className="w-full rounded-lg border border-astro-accent/50 bg-astro-accent/20 px-3 py-2 text-sm text-astro-text transition-colors hover:bg-astro-accent/30 disabled:opacity-50"
      >
        {locating ? "Locating..." : "Use my location"}
      </button>
      {geoError && <p className="text-xs text-amber-300">{geoError}</p>}

      <div className="space-y-1">
        <div className="flex justify-between text-xs text-astro-muted">
          <span>Search radius</span>
          <span>{rangeKm} km</span>
        </div>
        <input
          type="range"
          min={10}
          max={800}
          step={10}
          value={rangeKm}
          onChange={(event) => onRangeChange(Number(event.target.value))}
          className="w-full"
        />
      </div>

      <p className="text-[11px] text-astro-muted">
        Origin: {lat.toFixed(3)}, {lon.toFixed(3)}
      </p>
    </div>
  );
}
