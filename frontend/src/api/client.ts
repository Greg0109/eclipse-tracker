import type {
  Eclipse,
  ItineraryParams,
  ItineraryResponse,
  NominatimResult,
  RecommendationRequest,
  RecommendationResponse,
} from "../types/api";

// `||`, not `??`: an unset build variable arrives as an empty string, not undefined (CI passes
// `VITE_API_BASE_URL: ${{ vars.VITE_API_BASE_URL }}`, which expands to ""). With `??` that empty
// string won, so every call went to the page's own origin - on GitHub Pages that meant
// https://<user>.github.io/api/... answering 404 and 405 instead of the API.
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL?.trim() || "http://localhost:8080";

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, init);
  } catch {
    // fetch() rejects with a bare "Failed to fetch" for DNS/refused/CORS/mixed-content failures,
    // which tells the user nothing about which backend was even being called.
    throw new Error(`Could not reach the Eclipse Tracker API at ${API_BASE_URL}. Is the backend running?`);
  }
  if (!response.ok) {
    throw new Error(`${init?.method ?? "GET"} ${path} failed: ${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

export async function getNextEclipse(): Promise<Eclipse> {
  try {
    return await requestJson<Eclipse>("/api/eclipses/next");
  } catch {
    // The eclipse dataset is static and bundled, so the map and totality path can still be drawn
    // with no backend at all - which is exactly the case on the GitHub Pages build. Only the
    // recommendation and itinerary endpoints genuinely require the API to be running.
    const response = await fetch(`${import.meta.env.BASE_URL}data/next-eclipse.json`);
    if (!response.ok) throw new Error(`Could not load the bundled eclipse dataset: ${response.status}`);
    return response.json() as Promise<Eclipse>;
  }
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
