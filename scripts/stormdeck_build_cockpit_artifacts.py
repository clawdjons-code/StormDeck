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
from stormdeck_vertical_slice import build_vertical_slice_from_cfradial, build_vertical_slice_playlist

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


def build_vertical_slice_playlist_for_bundle(
    bundle_root: Path,
    *,
    field: str = "REF",
    sweep: Optional[str] = None,
    sweep_index: int = 0,
    strict_compatible: bool = False,
    max_rays: int = 180,
    max_gates: int = 420,
) -> Optional[Dict[str, Any]]:
    index = read_json(bundle_root / "ppi_tprt_replay_index.json")
    files = resolve_volume_files(bundle_root, index)
    slices: List[Dict[str, Any]] = []
    for path in files:
        if not path.exists():
            continue
        try:
            slices.append(
                build_vertical_slice_from_cfradial(
                    path,
                    field=field,
                    sweep=sweep,
                    sweep_index=sweep_index,
                    max_rays=max_rays,
                    max_gates=max_gates,
                )
            )
        except ValueError as exc:
            if "native RHI-like geometry" not in str(exc):
                raise
            continue
    if not slices:
        return None
    return build_vertical_slice_playlist(slices, case_id=index.get("case_id"), field=field, strict_compatible=strict_compatible)


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
    parser.add_argument("--skip-vertical-slice", action="store_true", help="Do not attempt native RHI vertical-slice sidecar export")
    parser.add_argument("--vertical-slice-field", default=None, help="Field for vertical_slice_playlist.json; defaults to --field")
    parser.add_argument("--vertical-slice-sweep", default=None, help="Native RHI sweep group name for vertical slice")
    parser.add_argument("--vertical-slice-sweep-index", type=int, default=0)
    parser.add_argument("--vertical-slice-out", default="vertical_slice_playlist.json")
    parser.add_argument("--strict-vertical-slice-playlist", action="store_true", help="Fail on mixed native-RHI vertical slice playlists")
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

    if not args.skip_vertical_slice:
        vertical_playlist = build_vertical_slice_playlist_for_bundle(
            bundle_root,
            field=args.vertical_slice_field or args.field,
            sweep=args.vertical_slice_sweep,
            sweep_index=args.vertical_slice_sweep_index,
            strict_compatible=args.strict_vertical_slice_playlist,
            max_rays=args.max_rays,
            max_gates=args.max_gates,
        )
        if vertical_playlist is not None:
            vertical_out = bundle_root / args.vertical_slice_out
            vertical_out.write_text(json.dumps(vertical_playlist, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            print(f"wrote vertical slice playlist: {vertical_out}")
            print(f"vertical_slice_schema: {vertical_playlist['schema']}")
            print(f"vertical_slice_frames: {vertical_playlist['frame_count']}")
        else:
            print("vertical slice skipped: no native RHI sweep found")

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
