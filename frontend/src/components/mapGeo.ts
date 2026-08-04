import type { Feature, LineString, Polygon } from "geojson";
import type { PathPoint } from "../types/api";

const EARTH_RADIUS_KM = 6371.0088;

function toRad(deg: number): number {
  return (deg * Math.PI) / 180;
}

function toDeg(rad: number): number {
  return (rad * 180) / Math.PI;
}

/** Point `distanceKm` from (lat, lon) along `bearingDeg`, using great-circle spherical math. */
function destinationPoint(lat: number, lon: number, bearingDeg: number, distanceKm: number): [number, number] {
  const angularDistance = distanceKm / EARTH_RADIUS_KM;
  const bearing = toRad(bearingDeg);
  const phi1 = toRad(lat);
  const lambda1 = toRad(lon);

  const phi2 = Math.asin(
    Math.sin(phi1) * Math.cos(angularDistance) + Math.cos(phi1) * Math.sin(angularDistance) * Math.cos(bearing),
  );
  const lambda2 =
    lambda1 +
    Math.atan2(
      Math.sin(bearing) * Math.sin(angularDistance) * Math.cos(phi1),
      Math.cos(angularDistance) - Math.sin(phi1) * Math.sin(phi2),
    );

  return [toDeg(lambda2), toDeg(phi2)];
}

function bearingBetween(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const phi1 = toRad(lat1);
  const phi2 = toRad(lat2);
  const dLambda = toRad(lon2 - lon1);
  const x = Math.sin(dLambda) * Math.cos(phi2);
  const y = Math.cos(phi1) * Math.sin(phi2) - Math.sin(phi1) * Math.cos(phi2) * Math.cos(dLambda);
  return (toDeg(Math.atan2(x, y)) + 360) % 360;
}

export function centerlineToLineString(centerline: PathPoint[]): Feature<LineString> {
  return {
    type: "Feature",
    properties: {},
    geometry: {
      type: "LineString",
      coordinates: centerline.map((point) => [point.lon, point.lat]),
    },
  };
}

/** Ribbon polygon of totality width around the centerline, offsetting each sample perpendicular to its local heading. */
export function buildTotalityBand(centerline: PathPoint[]): Feature<Polygon> {
  const leftSide: [number, number][] = [];
  const rightSide: [number, number][] = [];

  centerline.forEach((point, index) => {
    const prev = centerline[Math.max(index - 1, 0)];
    const next = centerline[Math.min(index + 1, centerline.length - 1)];
    const bearing = bearingBetween(prev.lat, prev.lon, next.lat, next.lon);
    const halfWidthKm = point.path_width_km / 2;
    leftSide.push(destinationPoint(point.lat, point.lon, bearing - 90, halfWidthKm));
    rightSide.push(destinationPoint(point.lat, point.lon, bearing + 90, halfWidthKm));
  });

  const ring = [...leftSide, ...rightSide.reverse()];
  if (ring.length > 0) ring.push(ring[0]);

  return {
    type: "Feature",
    properties: {},
    geometry: { type: "Polygon", coordinates: [ring] },
  };
}

export function scoreColor(composite: number): string {
  const clamped = Math.max(0, Math.min(100, composite));
  const hue = 260 - (clamped / 100) * 200;
  return `hsl(${hue}, 85%, 60%)`;
}
