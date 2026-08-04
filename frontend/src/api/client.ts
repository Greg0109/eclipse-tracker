import type {
  Eclipse,
  ItineraryParams,
  ItineraryResponse,
  NominatimResult,
  RecommendationRequest,
  RecommendationResponse,
} from "../types/api";

export const LOCAL_API_BASE_URL = "http://localhost:8080";
const STORAGE_KEY = "eclipse-tracker.api-base-url";

// `?.trim() ?? ""`, never a bare `??` fallback: an unset build variable arrives as an empty string,
// not undefined (CI passes `VITE_API_BASE_URL: ${{ vars.VITE_API_BASE_URL }}`, which expands to "").
const BUILD_TIME_BASE_URL = import.meta.env.VITE_API_BASE_URL?.trim() ?? "";

function isLoopbackHost(hostname: string): boolean {
  return hostname === "localhost" || hostname === "127.0.0.1" || hostname === "[::1]";
}

function storedBaseUrl(): string {
  try {
    return window.localStorage.getItem(STORAGE_KEY)?.trim() ?? "";
  } catch {
    return ""; // private-mode / blocked storage - just behave as if nothing was saved
  }
}

/**
 * Where the API lives, or "" when this build has no backend to talk to.
 *
 * A page served from a *remote* host must never default to http://localhost:8080, because that is
 * the visitor's own machine, not the developer's. It can only ever work for whoever happens to be
 * running the backend locally, browsers block the mixed http/https request, and Firefox now warns
 * about it outright ("Local Network Access detected"). So loopback is only assumed when the page
 * itself is served from loopback; anywhere else it must be opted into explicitly.
 */
export function getApiBaseUrl(): string {
  if (BUILD_TIME_BASE_URL) return BUILD_TIME_BASE_URL;
  const stored = storedBaseUrl();
  if (stored) return stored;
  return isLoopbackHost(window.location.hostname) ? LOCAL_API_BASE_URL : "";
}

/** Opt this browser into a specific backend (persisted); pass "" to forget it. */
export function setApiBaseUrl(url: string): void {
  try {
    const trimmed = url.trim();
    if (trimmed) window.localStorage.setItem(STORAGE_KEY, trimmed);
    else window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Nothing to do - the caller still gets the in-memory behaviour for this page load.
  }
}

/** Raised instead of firing a request that has nowhere to go. */
export class ApiNotConfiguredError extends Error {
  constructor() {
    super("No Eclipse Tracker backend is configured for this site.");
    this.name = "ApiNotConfiguredError";
  }
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const baseUrl = getApiBaseUrl();
  if (!baseUrl) throw new ApiNotConfiguredError();

  let response: Response;
  try {
    response = await fetch(`${baseUrl}${path}`, init);
  } catch {
    // fetch() rejects with a bare "Failed to fetch" for DNS/refused/CORS/mixed-content failures,
    // which tells the user nothing about which backend was even being called.
    throw new Error(`Could not reach the Eclipse Tracker API at ${baseUrl}. Is the backend running?`);
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
