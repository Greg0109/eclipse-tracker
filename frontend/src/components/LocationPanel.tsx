import type { Candidate } from "../types/api";

interface LocationPanelProps {
  candidate: Candidate | null;
}

const SCORE_ROWS: { key: keyof Candidate["score"]; label: string }[] = [
  { key: "duration", label: "Duration" },
  { key: "viewing_angle", label: "Viewing angle" },
  { key: "beauty", label: "Scenery" },
  { key: "accessibility", label: "Accessibility" },
  { key: "distance", label: "Distance" },
];

export function LocationPanel({ candidate }: LocationPanelProps) {
  if (!candidate) {
    return (
      <div className="glass-panel w-80 rounded-2xl p-4 text-sm text-astro-muted">
        Select a marker on the map to see viewing details.
      </div>
    );
  }

  // Render in the *candidate's* timezone, not the viewer's: someone planning from London still
  // needs the Spanish wall-clock time of a Spanish viewing spot.
  const timeLabel = new Date(candidate.eclipse_time_utc).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: candidate.timezone,
    timeZoneName: "short",
  });

  return (
    <div className="glass-panel w-80 space-y-3 rounded-2xl p-4">
      <div>
        <h2 className="text-lg font-semibold text-astro-text">{candidate.name}</h2>
        <p className="text-xs uppercase tracking-wide text-astro-muted">{candidate.category}</p>
      </div>

      <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
        <dt className="text-astro-muted">Composite score</dt>
        <dd className="text-right font-medium">{candidate.score.composite.toFixed(0)} / 100</dd>
        <dt className="text-astro-muted">Totality</dt>
        <dd className="text-right">{candidate.totality_duration_s.toFixed(0)}s</dd>
        <dt className="text-astro-muted">Eclipse time (local)</dt>
        <dd className="text-right">{timeLabel}</dd>
        <dt className="text-astro-muted">Sun az / alt</dt>
        <dd className="text-right">
          {candidate.sun_azimuth_deg.toFixed(0)}&deg; / {candidate.sun_altitude_deg.toFixed(0)}&deg;
        </dd>
        <dt className="text-astro-muted">Horizon clearance</dt>
        <dd className="text-right">{candidate.horizon_clearance_deg.toFixed(1)}&deg;</dd>
        <dt className="text-astro-muted">Distance</dt>
        <dd className="text-right">{candidate.distance_km.toFixed(1)} km</dd>
      </dl>

      <div className="space-y-1.5">
        {SCORE_ROWS.map(({ key, label }) => {
          const value = candidate.score[key];
          const percent = Math.max(0, Math.min(1, value)) * 100;
          return (
            <div key={key}>
              <div className="mb-0.5 flex justify-between text-xs text-astro-muted">
                <span>{label}</span>
                <span>{percent.toFixed(0)}%</span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-white/10">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-astro-accent-2 to-astro-accent"
                  style={{ width: `${percent}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>

      <p className={candidate.is_accessible ? "text-xs text-emerald-300" : "text-xs text-amber-300"}>
        {candidate.accessibility_note}
      </p>
    </div>
  );
}
