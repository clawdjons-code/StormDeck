#!/usr/bin/env python3
"""Build a Godot/browser-readable StormDeck bundle manifest.

This converts the current file-based KATD PPI sample bundle into one flat
playlist-style manifest so an engine client can load JSON once and scrub frames
without understanding the exporter directory conventions.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

FIELDS = ("REF", "VEL", "SW")


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def volume_id_from_file(file_path: str) -> str:
    return Path(str(file_path)).name.removesuffix(".nc")


def format_angle_deg(value: Any, angle_type: str = "angle") -> str:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "—"
    return f"{numeric:.1f}° {angle_type or 'angle'}"


def format_range_km(value_m: Any) -> str:
    try:
        numeric = float(value_m)
    except (TypeError, ValueError):
        return "—"
    return f"{numeric / 1000.0:.1f} km"


def rel_posix(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def sweep_name(sweep: Dict[str, Any], index: int) -> str:
    return str(sweep.get("sweep_name") or sweep.get("name") or f"sweep_{index}")


def build_frames(root: Path, index: Dict[str, Any]) -> List[Dict[str, Any]]:
    frames: List[Dict[str, Any]] = []
    for volume_ordinal, volume in enumerate(index.get("volumes") or []):
        volume_id = volume_id_from_file(volume.get("file", ""))
        manifest_path = root / "volumes" / volume_id / "manifest.json"
        manifest = read_json(manifest_path)
        for sweep_ordinal, sweep in enumerate(manifest.get("sweeps") or []):
            name = sweep_name(sweep, sweep_ordinal)
            for field in FIELDS:
                quicklook = root / "volumes" / volume_id / "quicklooks" / f"{name}_{field}.png"
                frames.append(
                    {
                        "frame_id": f"{volume_ordinal:03d}_{name}_{field}",
                        "volume_ordinal": volume_ordinal,
                        "volume_id": volume_id,
                        "volume_start_time": volume.get("start_time") or manifest.get("start_time"),
                        "volume_end_time": volume.get("end_time") or manifest.get("end_time"),
                        "scan_name": volume.get("scan_name") or manifest.get("scan_name"),
                        "scan_mode": (volume.get("scan_modes") or [index.get("scan_mode") or "sector"])[0],
                        "volume_type": manifest.get("volume_type"),
                        "sweep_ordinal": sweep_ordinal,
                        "sweep_name": name,
                        "field": field,
                        "quicklook_path": rel_posix(quicklook, root),
                        "quicklook_exists": quicklook.exists(),
                        "fixed_angle_type": sweep.get("fixed_angle_type"),
                        "fixed_angle_deg": sweep.get("fixed_angle_deg"),
                        "fixed_angle_display": format_angle_deg(sweep.get("fixed_angle_deg"), sweep.get("fixed_angle_type", "angle")),
                        "ray_count": sweep.get("ray_count"),
                        "gate_count": sweep.get("gate_count"),
                        "range_last_gate_m": (sweep.get("range") or {}).get("last_gate_m"),
                        "range_display": format_range_km((sweep.get("range") or {}).get("last_gate_m")),
                        "nyquist_mps": (sweep.get("nyquist_velocity") or {}).get("median_mps"),
                        "provenance": "observed_native_quicklook_png",
                        "interpretation_limit": "sample_browse_only_not_time_continuous_storm_motion",
                    }
                )
    return frames


def build_bundle_manifest(root: Path) -> Dict[str, Any]:
    root = Path(root).expanduser().resolve()
    index_path = root / "ppi_tprt_replay_index.json"
    index = read_json(index_path)
    validation_path = root / "bundle_validation.json"
    validation = read_json(validation_path) if validation_path.exists() else {"status": "not_run"}
    frames = build_frames(root, index)
    sidecars = {
        "field_preview_playlist": {"path": "field_preview_playlist.json", "schema": "stormdeck.field_preview_playlist.v0", "exists": (root / "field_preview_playlist.json").exists()},
        "vertical_slice_playlist": {"path": "vertical_slice_playlist.json", "schema": "stormdeck.vertical_slice_playlist.v0", "exists": (root / "vertical_slice_playlist.json").exists()},
        "map_overlays": {"path": "map_overlays.json", "schema": "stormdeck.map_overlays.v0", "exists": (root / "map_overlays.json").exists()},
    }
    return {
        "schema": "stormdeck.bundle_manifest.v0",
        "bundle_root_hint": ".",
        "source_index": "ppi_tprt_replay_index.json",
        "source_validation": "bundle_validation.json" if validation_path.exists() else None,
        "case_id": index.get("case_id"),
        "purpose": index.get("purpose"),
        "scan_name": index.get("scan_name"),
        "scan_mode": index.get("scan_mode"),
        "fields": list(FIELDS),
        "sidecars": sidecars,
        "volume_count": len(index.get("volumes") or []),
        "frame_count": len(frames),
        "validation": {
            "status": validation.get("status"),
            "quicklook_count": validation.get("quicklook_count"),
            "missing_quicklook_count": validation.get("missing_quicklook_count"),
        },
        "compatibility": {
            "temporal_comparison": "sample_browse_only",
            "animation_semantics": "frame_browsing_not_storm_motion",
            "rhi_included": False,
            "native_geometry": True,
            "gridded_3d": False,
        },
        "consumer_hints": {
            "godot_resource_loader": "json_plus_relative_png_paths",
            "texture_path_base": ".",
            "sort_order": ["volume_ordinal", "sweep_ordinal", "field"],
            "keyboard_controls": {"left_right": "sweep", "up_down": "field", "space": "volume"},
        },
        "warnings": list(index.get("warnings") or [])
        + ["Observed quicklook PNGs only; not gridded 3D volume rendering."],
        "frames": frames,
    }


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build stormdeck_bundle_manifest.json for a replay bundle.")
    parser.add_argument("bundle_root", help="Path to KATD_sample_inventory export bundle")
    parser.add_argument("--out", default=None, help="Output manifest path; defaults to <bundle_root>/stormdeck_bundle_manifest.json")
    args = parser.parse_args(argv)
    root = Path(args.bundle_root).expanduser().resolve()
    out = Path(args.out).expanduser().resolve() if args.out else root / "stormdeck_bundle_manifest.json"
    manifest = build_bundle_manifest(root)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote bundle manifest: {out}")
    print(f"schema: {manifest['schema']}")
    print(f"volumes: {manifest['volume_count']}")
    print(f"frames: {manifest['frame_count']}")
    print(f"validation_status: {manifest['validation']['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
