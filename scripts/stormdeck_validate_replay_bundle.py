#!/usr/bin/env python3
"""Validate a StormDeck file-based replay bundle.

This is intentionally dependency-free so it can run on wea-fs next to the exported
KATD sample bundle. It verifies the browser contract rather than meteorology:
index -> volume manifest -> sweep/field quicklook PNGs.
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


def _sweep_name(sweep: Dict[str, Any], fallback_index: int) -> str:
    return str(sweep.get("sweep_name") or sweep.get("name") or f"sweep_{fallback_index}")


def validate_volume(root: Path, volume: Dict[str, Any]) -> Dict[str, Any]:
    volume_id = volume_id_from_file(volume.get("file", ""))
    volume_dir = root / "volumes" / volume_id
    manifest_path = volume_dir / "manifest.json"
    result: Dict[str, Any] = {
        "volume_id": volume_id,
        "manifest_path": str(manifest_path),
        "manifest_exists": manifest_path.exists(),
        "status": "ready",
        "quicklook_count": 0,
        "missing_quicklook_count": 0,
        "missing_quicklooks": [],
        "sweeps": [],
    }
    if not manifest_path.exists():
        result["status"] = "incomplete"
        result["error"] = "missing manifest.json"
        return result

    manifest = read_json(manifest_path)
    result["volume_type"] = manifest.get("volume_type")
    for index, sweep in enumerate(manifest.get("sweeps") or []):
        name = _sweep_name(sweep, index)
        missing: List[str] = []
        present: List[str] = []
        for field in FIELDS:
            filename = f"{name}_{field}.png"
            if (volume_dir / "quicklooks" / filename).exists():
                present.append(filename)
            else:
                missing.append(filename)
        result["quicklook_count"] += len(present)
        result["missing_quicklook_count"] += len(missing)
        result["missing_quicklooks"].extend(missing)
        result["sweeps"].append(
            {
                "name": name,
                "fixed_angle_display": format_angle_deg(sweep.get("fixed_angle_deg"), sweep.get("fixed_angle_type", "angle")),
                "range_display": format_range_km((sweep.get("range") or {}).get("last_gate_m")),
                "rays_gates": f"{sweep.get('ray_count', '—')} × {sweep.get('gate_count', '—')}",
                "present_quicklooks": present,
                "missing_quicklooks": missing,
            }
        )
    if result["missing_quicklook_count"] or not result["sweeps"]:
        result["status"] = "incomplete"
    return result


def validate_bundle(root: Path) -> Dict[str, Any]:
    root = Path(root).expanduser().resolve()
    index_path = root / "ppi_tprt_replay_index.json"
    report: Dict[str, Any] = {
        "schema": "stormdeck.replay_bundle_validation.v0",
        "bundle_root": str(root),
        "index_path": str(index_path),
        "index_exists": index_path.exists(),
        "status": "ready",
        "volume_count": 0,
        "quicklook_count": 0,
        "missing_quicklook_count": 0,
        "volumes": [],
        "warnings": [
            "Validation confirms file contract only; it does not make the sample volumes time-continuous storm evidence."
        ],
    }
    if not index_path.exists():
        report["status"] = "incomplete"
        report["error"] = "missing ppi_tprt_replay_index.json"
        return report
    index = read_json(index_path)
    if index.get("schema") != "stormdeck.ppi_replay_index.v0":
        report["status"] = "incomplete"
        report["error"] = f"unexpected index schema: {index.get('schema')}"
        return report
    volumes = index.get("volumes") or []
    report["case_id"] = index.get("case_id")
    report["volume_count"] = len(volumes)
    for volume in volumes:
        volume_report = validate_volume(root, volume)
        report["volumes"].append(volume_report)
        report["quicklook_count"] += volume_report.get("quicklook_count", 0)
        report["missing_quicklook_count"] += volume_report.get("missing_quicklook_count", 0)
        if volume_report.get("status") != "ready":
            report["status"] = "incomplete"
    return report


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a StormDeck PPI replay bundle directory.")
    parser.add_argument("bundle_root", help="Path to KATD_sample_inventory export bundle")
    parser.add_argument("--out", default=None, help="Optional JSON report output path")
    args = parser.parse_args(argv)

    report = validate_bundle(Path(args.bundle_root))
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.out:
        out = Path(args.out).expanduser().resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(f"wrote validation report: {out}")
    print(f"status: {report['status']}")
    print(f"volumes: {report['volume_count']}")
    print(f"quicklooks: {report['quicklook_count']}")
    print(f"missing_quicklooks: {report['missing_quicklook_count']}")
    return 0 if report["status"] == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
