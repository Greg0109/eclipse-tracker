import { useEffect, useRef } from "react";
import { LngLatBounds, Map as MapLibreMap, Marker, NavigationControl, Popup, type GeoJSONSource } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { Candidate, Eclipse } from "../types/api";
import { buildTotalityBand, centerlineToLineString, scoreColor } from "./mapGeo";

const MAP_STYLE_URL = "https://tiles.openfreemap.org/styles/dark";

interface MapViewProps {
  eclipse: Eclipse | null;
  candidates: Candidate[];
  selectedCandidateId: string | null;
  onSelectCandidate: (candidate: Candidate) => void;
}

export function MapView({ eclipse, candidates, selectedCandidateId, onSelectCandidate }: MapViewProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const markersRef = useRef<Marker[]>([]);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = new MapLibreMap({
      container: containerRef.current,
      style: MAP_STYLE_URL,
      center: [0, 30],
      zoom: 2,
    });
    map.addControl(new NavigationControl(), "top-right");
    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !eclipse || eclipse.centerline.length === 0) return;

    const applyEclipseLayers = () => {
      const lineFeature = centerlineToLineString(eclipse.centerline);
      const bandFeature = buildTotalityBand(eclipse.centerline);

      const bandSource = map.getSource("totality-band") as GeoJSONSource | undefined;
      if (bandSource) {
        bandSource.setData(bandFeature);
      } else {
        map.addSource("totality-band", { type: "geojson", data: bandFeature });
        map.addLayer({
          id: "totality-band-fill",
          type: "fill",
          source: "totality-band",
          paint: { "fill-color": "#a78bfa", "fill-opacity": 0.12 },
        });
      }

      const lineSource = map.getSource("centerline") as GeoJSONSource | undefined;
      if (lineSource) {
        lineSource.setData(lineFeature);
      } else {
        map.addSource("centerline", { type: "geojson", data: lineFeature });
        map.addLayer({
          id: "centerline-line",
          type: "line",
          source: "centerline",
          layout: { "line-cap": "round" },
          paint: { "line-color": "#38bdf8", "line-width": 2, "line-dasharray": [1, 2] },
        });
      }

      const first = eclipse.centerline[0];
      const bounds = eclipse.centerline.reduce(
        (acc, point) => acc.extend([point.lon, point.lat]),
        new LngLatBounds([first.lon, first.lat], [first.lon, first.lat]),
      );
      map.fitBounds(bounds, { padding: 60, maxZoom: 5, duration: 800 });
    };

    if (map.isStyleLoaded()) {
      applyEclipseLayers();
    } else {
      map.once("load", applyEclipseLayers);
    }
  }, [eclipse]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    markersRef.current.forEach((marker) => marker.remove());

    markersRef.current = candidates.map((candidate) => {
      const isSelected = candidate.id === selectedCandidateId;
      const el = document.createElement("div");
      const size = 10 + (candidate.score.composite / 100) * 16;
      el.style.width = `${size}px`;
      el.style.height = `${size}px`;
      el.style.borderRadius = "50%";
      el.style.cursor = "pointer";
      el.style.background = scoreColor(candidate.score.composite);
      el.style.border = isSelected ? "2px solid #fff" : "1px solid rgba(255,255,255,0.4)";
      el.style.boxShadow = isSelected ? "0 0 14px rgba(255,255,255,0.85)" : "0 0 6px rgba(0,0,0,0.5)";
      el.style.transition = "transform 0.15s ease";
      el.addEventListener("mouseenter", () => {
        el.style.transform = "scale(1.2)";
      });
      el.addEventListener("mouseleave", () => {
        el.style.transform = "scale(1)";
      });
      el.addEventListener("click", () => onSelectCandidate(candidate));

      return new Marker({ element: el })
        .setLngLat([candidate.lon, candidate.lat])
        .setPopup(new Popup({ offset: 14, closeButton: false }).setText(candidate.name))
        .addTo(map);
    });

    return () => {
      markersRef.current.forEach((marker) => marker.remove());
    };
  }, [candidates, selectedCandidateId, onSelectCandidate]);

  // Inline style, not a Tailwind class: maplibre-gl.css sets `.maplibregl-map { position: relative }`
  // as plain unlayered CSS, which beats Tailwind's `absolute` utility (scoped inside `@layer utilities`)
  // regardless of import order, collapsing this container to 0 height. Inline styles outrank both.
  return <div ref={containerRef} style={{ position: "absolute", inset: 0 }} />;
}
