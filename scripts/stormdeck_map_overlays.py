#!/usr/bin/env python3
"""Generate StormDeck map overlay context JSON from a small case config.

This generator does not read radar gates, grid radar data, or validate active
warning products. It turns explicit operator/training context into
stormdeck.map_overlays.v0 so the replay viewer can draw towns, schematic
corridors, and optional boundary linework on the orientation sketch only.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

CONFIG_SCHEMA = "stormdeck.map_overlay_config.v0"
OUTPUT_SCHEMA = "stormdeck.map_overlays.v0"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def overlay_list(value: Any) -> List[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def load_json(path: Optional[str]) -> Any:
    if not path:
        return []
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def normalize_boundary_features(payload: Any) -> List[Dict[str, Any]]:
    """Return lightweight line records from either existing records or GeoJSON.

    v0 intentionally keeps this permissive and small. If no boundary source is
    provided, callers get an empty list. If GeoJSON is supplied, LineString and
    Polygon rings are converted to points the viewer already understands.
    """
    if not payload:
        return []
    if isinstance(payload, list):
        return payload
    features = payload.get("features") if isinstance(payload, dict) else None
    if not features:
        return overlay_list(payload)

    lines: List[Dict[str, Any]] = []
    for feature in features:
        geometry = feature.get("geometry") or {}
        properties = feature.get("properties") or {}
        geom_type = geometry.get("type")
        coords = geometry.get("coordinates") or []
        coordinate_lines: List[Any] = []
        if geom_type == "LineString":
            coordinate_lines = [coords]
        elif geom_type == "MultiLineString":
            coordinate_lines = coords
        elif geom_type == "Polygon":
            coordinate_lines = coords[:1]
        elif geom_type == "MultiPolygon":
            coordinate_lines = [polygon[0] for polygon in coords if polygon]
        for index, line in enumerate(coordinate_lines):
            points = [
                {"longitude_deg": pair[0], "latitude_deg": pair[1]}
                for pair in line
                if isinstance(pair, list) and len(pair) >= 2
            ]
            if len(points) >= 2:
                lines.append({
                    "id": properties.get("id") or properties.get("name") or f"boundary-{len(lines) + 1}",
                    "name": properties.get("name"),
                    "ring_index": index,
                    "points": points,
                })
    return lines


def normalize_warning_corridor(corridor: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(corridor)
    normalized.setdefault("source", "manual-demo")
    normalized.setdefault("active_product", False)
    normalized.setdefault("confidence", "schematic context")
    normalized.setdefault(
        "caveat",
        "Schematic context only; not an active warning product unless source metadata says so.",
    )
    return normalized


def build_map_overlays(config: Dict[str, Any], *, generated_at: Optional[str] = None) -> Dict[str, Any]:
    schema = config.get("schema")
    if schema != CONFIG_SCHEMA:
        raise ValueError(f"expected {CONFIG_SCHEMA}, got {schema!r}")

    warning_corridors = [normalize_warning_corridor(c) for c in overlay_list(config.get("warning_corridors"))]
    source_kind = config.get("source") or next((c.get("source") for c in warning_corridors if c.get("source")), "manual-demo")
    active_warning_product = any(bool(c.get("active_product")) for c in warning_corridors)
    boundary_sources = config.get("boundary_sources") or {}

    return {
        "schema": OUTPUT_SCHEMA,
        "description": "Generated context overlays for the StormDeck orientation sketch. These overlays do not grid, alter, or project radar gate values.",
        "source": {
            "kind": source_kind,
            "site": config.get("site"),
            "generated_at": generated_at or utc_now_iso(),
            "active_warning_product": active_warning_product,
            "caveat": "Map overlays are context only; radar gates remain native polar observations.",
        },
        "town_points": overlay_list(config.get("towns") or config.get("town_points")),
        "warning_corridors": warning_corridors,
        "county_boundaries": normalize_boundary_features(load_json(boundary_sources.get("county_geojson"))),
        "state_boundaries": normalize_boundary_features(load_json(boundary_sources.get("state_geojson"))),
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Generate stormdeck.map_overlays.v0 from a map overlay config.")
    parser.add_argument("--config", required=True, help="Path to stormdeck.map_overlay_config.v0 JSON")
    parser.add_argument("--out", required=True, help="Output path for map_overlays.json")
    args = parser.parse_args(argv)

    config_path = Path(args.config)
    output_path = Path(args.out)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    overlays = build_map_overlays(config)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(overlays, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
