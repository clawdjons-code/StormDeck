#!/usr/bin/env python3
"""Build a StormDeck case manifest that bundles replay cockpit export artifacts."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


ARTIFACT_SLOTS = {
    "case_timeline": {
        "filenames": ["case_timeline.json"],
        "schemas": ["stormdeck.case_timeline.v0"],
        "required": True,
    },
    "temporal_tracks": {
        "filenames": ["temporal_tracks.json"],
        "schemas": ["stormdeck.temporal_tracks.v0"],
        "required": True,
    },
    "change_summary": {
        "filenames": ["change_summary.json"],
        "schemas": ["stormdeck.change_summary.v0"],
        "required": True,
    },
    "field_preview": {
        "filenames": ["field_preview_playlist.json", "field_preview.json"],
        "schemas": ["stormdeck.field_preview_playlist.v0", "stormdeck.field_preview.v0"],
        "required": True,
    },
    "map_overlays": {
        "filenames": ["map_overlays.json"],
        "schemas": ["stormdeck.map_overlays.v0"],
        "required": False,
    },
}


def load_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc


def artifact_payload(export_dir: Path, slot: str, spec: Dict[str, Any]) -> Dict[str, Any]:
    for filename in spec["filenames"]:
        path = export_dir / filename
        if not path.exists():
            continue
        payload = load_json(path)
        schema = payload.get("schema")
        status = "ready" if schema in spec["schemas"] else "schema_mismatch"
        return {
            "slot": slot,
            "filename": filename,
            "relative_path": filename,
            "exists": True,
            "required": bool(spec["required"]),
            "schema": schema,
            "expected_schemas": spec["schemas"],
            "status": status,
            "case_id": payload.get("case_id"),
            "summary": summarize_payload(payload),
        }
    return {
        "slot": slot,
        "filename": spec["filenames"][0],
        "relative_path": spec["filenames"][0],
        "exists": False,
        "required": bool(spec["required"]),
        "schema": None,
        "expected_schemas": spec["schemas"],
        "status": "missing",
        "case_id": None,
        "summary": {},
    }


def summarize_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    schema = payload.get("schema")
    if schema == "stormdeck.field_preview_playlist.v0":
        return {
            "frame_count": payload.get("frame_count"),
            "compatibility": payload.get("compatibility", {}).get("status"),
            "timeline": payload.get("timeline"),
        }
    if schema == "stormdeck.field_preview.v0":
        return {
            "field": payload.get("field", {}).get("name"),
            "scan_name": payload.get("display_metadata", {}).get("scan_name"),
        }
    if schema == "stormdeck.map_overlays.v0":
        return {
            "town_points": len(payload.get("town_points", [])),
            "warning_corridors": len(payload.get("warning_corridors", [])),
        }
    return {}


def readiness_for(artifacts: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    missing_required = [slot for slot, artifact in artifacts.items() if artifact["required"] and artifact["status"] != "ready"]
    missing_optional = [slot for slot, artifact in artifacts.items() if not artifact["required"] and artifact["status"] != "ready"]
    loaded_required = [slot for slot, artifact in artifacts.items() if artifact["required"] and artifact["status"] == "ready"]
    required_count = sum(1 for artifact in artifacts.values() if artifact["required"])
    loaded_exports = [slot for slot, artifact in artifacts.items() if artifact["status"] == "ready"]
    return {
        "status": "ready" if not missing_required else "blocked",
        "expected_export_count": len(artifacts),
        "loaded_export_count": len(loaded_exports),
        "required_count": required_count,
        "loaded_required_count": len(loaded_required),
        "missing_required": missing_required,
        "missing_optional": missing_optional,
        "operator_note": "Cockpit can be armed from manifest." if not missing_required else "Manifest is missing required cockpit exports.",
    }


def build_case_manifest(
    *,
    export_dir: Path,
    case_id: str,
    source_root: Optional[str] = None,
) -> Dict[str, Any]:
    export_dir = Path(export_dir).expanduser().resolve()
    artifacts = {slot: artifact_payload(export_dir, slot, spec) for slot, spec in ARTIFACT_SLOTS.items()}
    return {
        "schema": "stormdeck.case_manifest.v0",
        "case_id": case_id,
        "source_root": source_root,
        "export_dir": str(export_dir),
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "artifacts": artifacts,
        "readiness": readiness_for(artifacts),
        "viewer_hints": {
            "serving_note": "Browser can fetch artifacts when served from the export directory; file:// use still requires manual file selection.",
            "preferred_loader": "stormdeck_case_manifest.json",
        },
        "warnings": [
            "Manifest references browser-safe JSON exports only; raw radar data remains on the data host.",
            "Viewer must still display per-artifact caveats, confidence, uncertainty, and playlist compatibility.",
        ],
    }


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build stormdeck.case_manifest.v0 for a cockpit export bundle.")
    parser.add_argument("--export-dir", required=True, help="Directory containing StormDeck JSON exports")
    parser.add_argument("--case-id", required=True, help="Case identifier")
    parser.add_argument("--source-root", default=None, help="Original radar/source data root, if known")
    parser.add_argument("--out", required=True, help="Output stormdeck_case_manifest.json path")
    args = parser.parse_args(argv)

    manifest = build_case_manifest(export_dir=Path(args.export_dir), case_id=args.case_id, source_root=args.source_root)
    out = Path(args.out).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote case manifest: {out}")
    print(f"Readiness: {manifest['readiness']['status']} ({manifest['readiness']['loaded_required_count']}/{manifest['readiness']['required_count']} required)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
