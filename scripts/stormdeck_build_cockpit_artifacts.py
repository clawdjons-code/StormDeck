#!/usr/bin/env python3
"""Build the browser cockpit's real-data sidecar artifacts for a replay bundle.

Given a bundle root containing ``ppi_tprt_replay_index.json``, this helper writes:

- ``field_preview_playlist.json`` from observed native CfRadial gates;
- ``map_overlays.json`` from a StormDeck map overlay config, when available.

It is intentionally a thin orchestrator around the existing exporters so Bryan/wea-fs
can refresh the honest cockpit data layer with one command after generating quicklook
PNGs and ``stormdeck_bundle_manifest.json``.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from stormdeck_field_preview import (
    build_field_preview_from_cfradial,
    build_field_preview_playlist,
    filter_playlist_previews,
)
from stormdeck_map_overlays import build_map_overlays

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MAP_CONFIG = ROOT / "examples" / "map_overlay_config.sample.json"


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_volume_files(bundle_root: Path, index: Dict[str, Any]) -> List[Path]:
    files: List[Path] = []
    for volume in index.get("volumes") or []:
        raw = volume.get("file") or volume.get("path") or volume.get("source_path")
        if not raw:
            continue
        path = Path(str(raw)).expanduser()
        if not path.is_absolute():
            path = (bundle_root / path).resolve()
        files.append(path)
    return files


def build_field_playlist_for_bundle(
    bundle_root: Path,
    *,
    field: str = "REF",
    sweep: Optional[str] = None,
    sweep_index: int = 0,
    scan_name: Optional[str] = None,
    playlist_sweep_name: Optional[str] = None,
    strict_compatible: bool = False,
    max_rays: int = 240,
    max_gates: int = 480,
) -> Dict[str, Any]:
    index = read_json(bundle_root / "ppi_tprt_replay_index.json")
    files = resolve_volume_files(bundle_root, index)
    if not files:
        raise ValueError("No source CfRadial files found in ppi_tprt_replay_index.json volumes[].file")
    missing = [str(path) for path in files if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Source CfRadial file(s) missing: {missing}")
    previews = [
        build_field_preview_from_cfradial(
            path,
            field=field,
            sweep=sweep,
            sweep_index=sweep_index,
            max_rays=max_rays,
            max_gates=max_gates,
        )
        for path in files
    ]
    previews = filter_playlist_previews(previews, scan_name=scan_name, sweep_name=playlist_sweep_name)
    if not previews:
        raise ValueError("No previews remain after scan/sweep filtering")
    return build_field_preview_playlist(
        previews,
        case_id=index.get("case_id"),
        field=field,
        strict_compatible=strict_compatible,
    )


def maybe_build_map_overlays(config_path: Optional[Path]) -> Optional[Dict[str, Any]]:
    if config_path is None:
        return None
    if not config_path.exists():
        raise FileNotFoundError(f"Map overlay config not found: {config_path}")
    return build_map_overlays(read_json(config_path))


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build field_preview_playlist.json and map_overlays.json for the StormDeck cockpit.")
    parser.add_argument("bundle_root", help="Replay bundle root containing ppi_tprt_replay_index.json")
    parser.add_argument("--field", default="REF", help="Observed field to export, e.g. REF, VEL, SW")
    parser.add_argument("--sweep", default=None, help="Sweep group name, e.g. sweep_0")
    parser.add_argument("--sweep-index", type=int, default=0, help="Sweep index if --sweep is omitted")
    parser.add_argument("--scan-name", default=None, help="Optional scan_name filter")
    parser.add_argument("--playlist-sweep-name", default=None, help="Optional selected sweep-name filter after preview export")
    parser.add_argument("--strict-compatible-playlist", action="store_true", help="Fail on mixed/non-comparable preview playlists")
    parser.add_argument("--max-rays", type=int, default=240)
    parser.add_argument("--max-gates", type=int, default=480)
    parser.add_argument("--field-preview-out", default="field_preview_playlist.json")
    parser.add_argument("--map-config", default=str(DEFAULT_MAP_CONFIG), help="stormdeck.map_overlay_config.v0 JSON; pass empty string to skip")
    parser.add_argument("--map-out", default="map_overlays.json")
    args = parser.parse_args(argv)

    bundle_root = Path(args.bundle_root).expanduser().resolve()
    playlist = build_field_playlist_for_bundle(
        bundle_root,
        field=args.field,
        sweep=args.sweep,
        sweep_index=args.sweep_index,
        scan_name=args.scan_name,
        playlist_sweep_name=args.playlist_sweep_name,
        strict_compatible=args.strict_compatible_playlist,
        max_rays=args.max_rays,
        max_gates=args.max_gates,
    )
    field_out = bundle_root / args.field_preview_out
    field_out.write_text(json.dumps(playlist, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote field preview playlist: {field_out}")
    print(f"field_preview_schema: {playlist['schema']}")
    print(f"field_preview_frames: {playlist['frame_count']}")

    config = Path(args.map_config).expanduser().resolve() if args.map_config else None
    overlays = maybe_build_map_overlays(config)
    if overlays is not None:
        map_out = bundle_root / args.map_out
        map_out.write_text(json.dumps(overlays, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"wrote map overlays: {map_out}")
        print(f"map_overlay_schema: {overlays['schema']}")
        print(f"town_points: {len(overlays.get('town_points') or [])}")
    else:
        print("map overlays skipped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
