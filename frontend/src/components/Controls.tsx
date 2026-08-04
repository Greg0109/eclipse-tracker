import { useState } from "react";
import { useGeolocation } from "../hooks/useGeolocation";

interface ControlsProps {
  lat: number;
  lon: number;
  rangeKm: number;
  searching: boolean;
  resolvedPlace: string | null;
  onRangeChange: (rangeKm: number) => void;
  onLocationChange: (lat: number, lon: number) => void;
  onSearch: (query: string) => void;
}

export function Controls({
  lat,
  lon,
  rangeKm,
  searching,
  resolvedPlace,
  onRangeChange,
  onLocationChange,
  onSearch,
}: ControlsProps) {
  const [query, setQuery] = useState("");

  const {
    loading: locating,
    error: geoError,
    locate,
  } = useGeolocation((foundLat, foundLon) => onLocationChange(foundLat, foundLon));

  return (
    <div className="glass-panel w-80 space-y-4 rounded-2xl p-4">
      <div>
        <h1 className="text-base font-semibold text-astro-text">Eclipse Tracker</h1>
        <p className="text-xs text-astro-muted">Find the best spot to watch totality.</p>
      </div>

      <div className="space-y-1">
        <label className="text-xs text-astro-muted" htmlFor="address-search">
          Place to search around
        </label>
        <input
          id="address-search"
          className="w-full rounded-lg border border-astro-border bg-white/5 px-3 py-2 text-sm text-astro-text placeholder:text-astro-muted focus:ring-1 focus:ring-astro-accent focus:outline-none"
          type="text"
          placeholder="City, address... (or use my location)"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !searching) onSearch(query);
          }}
        />
        {resolvedPlace && <p className="text-[11px] text-astro-muted">Found: {resolvedPlace}</p>}
      </div>

      <button
        type="button"
        onClick={locate}
        disabled={locating || searching}
        className="w-full rounded-lg border border-astro-border bg-white/5 px-3 py-2 text-sm text-astro-text transition-colors hover:bg-white/10 disabled:opacity-50"
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

      {/* The only thing that starts a recommendation run. Typing, moving the slider and picking a
          location all just stage the query - nothing hits the API until this is pressed. */}
      <button
        type="button"
        onClick={() => onSearch(query)}
        disabled={searching}
        className="w-full rounded-lg border border-astro-accent/50 bg-astro-accent/20 px-3 py-2 text-sm font-medium text-astro-text transition-colors hover:bg-astro-accent/30 disabled:opacity-50"
      >
        {searching ? "Searching..." : "Search"}
      </button>
    </div>
  );
}
