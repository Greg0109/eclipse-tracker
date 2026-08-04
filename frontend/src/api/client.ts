import type {
  Eclipse,
  ItineraryParams,
  ItineraryResponse,
  NominatimResult,
  RecommendationRequest,
  RecommendationResponse,
} from "../types/api";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8080";

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, init);
  if (!response.ok) {
    throw new Error(`${init?.method ?? "GET"} ${path} failed: ${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

export function getNextEclipse(): Promise<Eclipse> {
  return requestJson<Eclipse>("/api/eclipses/next");
}

export function listEclipses(): Promise<Eclipse[]> {
  return requestJson<Eclipse[]>("/api/eclipses");
}

export function getRecommendations(body: RecommendationRequest): Promise<RecommendationResponse> {
  return requestJson<RecommendationResponse>("/api/recommendations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function getItinerary(params: ItineraryParams): Promise<ItineraryResponse> {
  const query = new URLSearchParams({
    candidate_id: params.candidate_id,
    candidate_name: params.candidate_name,
    eclipse_id: params.eclipse_id,
    lat: String(params.lat),
    lon: String(params.lon),
  });
  return requestJson<ItineraryResponse>(`/api/itinerary?${query.toString()}`);
}

const NOMINATIM_URL = "https://nominatim.openstreetmap.org/search";

export async function searchAddress(query: string): Promise<NominatimResult[]> {
  const params = new URLSearchParams({ q: query, format: "jsonv2", limit: "5" });
  const response = await fetch(`${NOMINATIM_URL}?${params.toString()}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`Nominatim search failed: ${response.status}`);
  }
  return response.json() as Promise<NominatimResult[]>;
}
