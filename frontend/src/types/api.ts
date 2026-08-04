export type EclipseType = "total" | "annular" | "partial" | "hybrid";

export interface PathPoint {
  lat: number;
  lon: number;
  time_utc: string;
  totality_duration_s: number;
  path_width_km: number;
  sun_azimuth_deg: number;
  sun_altitude_deg: number;
}

export interface Eclipse {
  id: string;
  name: string;
  date: string;
  type: EclipseType;
  source_note: string;
  greatest_duration_s: number;
  centerline: PathPoint[];
}

export interface ScoreBreakdown {
  duration: number;
  distance: number;
  viewing_angle: number;
  beauty: number;
  accessibility: number;
  composite: number;
}

export interface ScoringWeights {
  duration: number;
  distance: number;
  viewing_angle: number;
  beauty: number;
  accessibility: number;
}

export interface Candidate {
  id: string;
  name: string;
  lat: number;
  lon: number;
  category: string;
  distance_km: number;
  totality_duration_s: number;
  eclipse_time_utc: string;
  /** Same instant as `eclipse_time_utc`, already offset into `timezone`. */
  eclipse_time_local: string;
  /** IANA zone at the candidate's own location, e.g. `Europe/Madrid`. */
  timezone: string;
  sun_azimuth_deg: number;
  sun_altitude_deg: number;
  horizon_clearance_deg: number;
  is_accessible: boolean;
  accessibility_note: string;
  tags: Record<string, string>;
  score: ScoreBreakdown;
}

export interface RecommendationRequest {
  lat: number;
  lon: number;
  range_km?: number;
  eclipse_id?: string | null;
  limit?: number;
  weights?: ScoringWeights | null;
}

export interface RecommendationResponse {
  eclipse: Eclipse;
  origin: [number, number];
  range_km: number;
  candidates: Candidate[];
  /** Degraded-result notes, e.g. the upstream OSM API being unreachable. */
  warnings: string[];
}

export interface ItineraryStop {
  kind: string;
  name: string;
  lat: number;
  lon: number;
  start_local_hint: string;
  note: string;
  tags: Record<string, string>;
}

export interface ItineraryResponse {
  candidate_id: string;
  eclipse_id: string;
  stops: ItineraryStop[];
}

export interface ItineraryParams {
  candidate_id: string;
  candidate_name: string;
  eclipse_id: string;
  lat: number;
  lon: number;
}

export interface NominatimResult {
  display_name: string;
  lat: string;
  lon: string;
}
