"""FastAPI dependency providers for the external-data services (singletons, from settings)."""

from __future__ import annotations

from functools import lru_cache

from eclipse_tracker.config.config import settings
from eclipse_tracker.services.osm_service import OsmService
from eclipse_tracker.services.terrain_service import TerrainService


@lru_cache
def get_osm_service() -> OsmService:
    """Singleton OSM/Overpass service, configured from settings.external_apis."""
    cfg = settings.external_apis
    return OsmService(
        overpass_urls=list(cfg.overpass_urls),
        user_agent=cfg.user_agent,
        timeout_s=cfg.request_timeout_s,
        cache_ttl_s=cfg.cache_ttl_s,
        max_concurrent_requests=cfg.max_concurrent_overpass_requests,
        batch_size=cfg.overpass_batch_size,
        hedge_delay_s=cfg.overpass_hedge_delay_s,
    )


@lru_cache
def get_terrain_service() -> TerrainService:
    """Singleton terrain/elevation service, configured from settings.external_apis + scoring."""
    cfg = settings.external_apis
    scoring = settings.scoring
    return TerrainService(
        elevation_url=cfg.elevation_url,
        user_agent=cfg.user_agent,
        timeout_s=cfg.request_timeout_s,
        cache_ttl_s=cfg.cache_ttl_s,
        ray_samples=scoring.terrain_ray_samples,
        ray_max_km=scoring.terrain_ray_max_km,
    )
