"""Maps raw OSM tags to the coarse category vocabulary used by scoring and the API."""

from __future__ import annotations


def classify(tags: dict[str, str]) -> str:  # noqa: PLR0911 - priority-ordered tag checks, clearer as early returns
    """Best-effort coarse category for an OSM node's tags."""
    if tags.get("tourism") == "viewpoint":
        return "viewpoint"
    if tags.get("natural") == "peak":
        return "peak"
    if tags.get("natural") == "beach":
        return "beach"
    if tags.get("leisure") == "park":
        return "park"
    if "historic" in tags:
        return "historic"
    if tags.get("tourism") == "attraction":
        return "attraction"
    return "poi"
