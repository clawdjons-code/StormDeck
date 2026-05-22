#!/usr/bin/env python3
"""Convert a StormDeck case-probe manifest into an engine-facing volume index.

The case-probe manifest is intentionally verbose and diagnostic. This script
emits a smaller contract that a renderer/backend can consume without knowing all
probe internals. It preserves radar geometry facts that matter operationally:
scan type, fixed angle, variable ray counts, gate counts, field stats, quicklook
paths, source provenance, and observed-data caveats.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Dict, Optional


def json_safe(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    return value


def relative_to_manifest(path_text: Optional[str], manifest_path: Optional[Path]) -> Optional[str]:
    if not path_text:
        return None
    path = Path(path_text)
    if manifest_path is None:
        return path.name
    base = manifest_path.expanduser().resolve().parent
    try:
        return str(path.expanduser().resolve().relative_to(base))
    except Exception:
        return path.name


def render_lookup(sweep: Dict[str, Any], manifest_path: Optional[Path]) -> Dict[str, str]:
    lookup: Dict[str, str] = {}
    for render in sweep.get("renders", []) or []:
        png = render.get("png")
        if not png:
            continue
        stem = Path(str(png)).stem
        # Quicklooks produced by stormdeck_case_probe use sweep_N_FIELD.png.
        field = stem.rsplit("_", 1)[-1]
        lookup[field] = relative_to_manifest(str(png), manifest_path) or str(png)
    return lookup


def build_field_index(field_name: str, field: Dict[str, Any], quicklook_png: Optional[str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {"present": bool(field.get("present"))}
    if not out["present"]:
        return out
    for key in (
        "source_variable",
        "dtype",
        "units",
        "long_name",
        "shape",
        "valid_gate_count",
        "missing_gate_count",
        "min",
        "max",
        "mean",
        "p01",
        "p50",
        "p99",
    ):
        if key in field:
            out[key] = field[key]
    out["display_name"] = field_name
    out["quicklook_png"] = quicklook_png
    return json_safe(out)


def build_sweep_index(sweep: Dict[str, Any], manifest_path: Optional[Path]) -> Dict[str, Any]:
    quicklooks = render_lookup(sweep, manifest_path)
    fields = {
        field_name: build_field_index(field_name, field, quicklooks.get(field_name))
        for field_name, field in sorted((sweep.get("fields") or {}).items())
    }
    return json_safe(
        {
            "sweep_name": sweep.get("sweep_name"),
            "scan_type": sweep.get("scan_type"),
            "fixed_angle_type": sweep.get("fixed_angle_type"),
            "fixed_angle_deg": sweep.get("fixed_angle_deg"),
            "ray_count": sweep.get("ray_count"),
            "gate_count": sweep.get("gate_count"),
            "range": sweep.get("range"),
            "time": sweep.get("time"),
            "nyquist_velocity": sweep.get("nyquist_velocity"),
            "fields": fields,
        }
    )


def build_volume_index(manifest: Dict[str, Any], manifest_path: Optional[Path] = None) -> Dict[str, Any]:
    sweeps = manifest.get("sweeps") or []
    sweep_count = int(manifest.get("sweep_count") or len(sweeps))
    duration_s = manifest.get("duration_s_from_offsets")
    average_seconds_per_sweep = None
    if isinstance(duration_s, (int, float)) and sweep_count > 0:
        average_seconds_per_sweep = float(duration_s) / sweep_count

    ray_counts = [s.get("ray_count") for s in sweeps if s.get("ray_count") is not None]
    gate_counts = [s.get("gate_count") for s in sweeps if s.get("gate_count") is not None]
    ray_counts_vary = len(set(ray_counts)) > 1
    gate_counts_vary = len(set(gate_counts)) > 1

    index = {
        "schema": "stormdeck.volume_index.v0",
        "source": {
            "file": manifest.get("source_nc"),
            "format": manifest.get("source_format"),
            "radar_id": manifest.get("radar_id"),
            "site_name": manifest.get("site_name"),
            "scan_name": manifest.get("scan_name"),
            "case_probe_schema": manifest.get("stormdeck_schema"),
        },
        "volume": {
            "type": manifest.get("volume_type"),
            "sweep_count": sweep_count,
            "duration_s": duration_s,
            "average_seconds_per_sweep": average_seconds_per_sweep,
            "start_time": manifest.get("start_time") or manifest.get("time_coverage_start"),
            "end_time": manifest.get("end_time") or manifest.get("time_coverage_end"),
            "scientific_status": manifest.get("scientific_status"),
        },
        "engine_hints": {
            "ray_counts_vary_by_sweep": ray_counts_vary,
            "gate_counts_vary_by_sweep": gate_counts_vary,
            "assume_uniform_ray_count": False,
            "assume_uniform_gate_count": not gate_counts_vary,
            "geometry_model": (manifest.get("adaptive_scan") or {}).get("geometry_model", "regular_sweep"),
            "observed_native_gates_only": True,
        },
        "client_contract": {
            "quicklooks_are_preview_only": True,
            "quicklooks_are_not_gridded": True,
            "distinguish_observed_from_inferred": True,
            "display_required_metadata": ["source.file", "volume.start_time", "volume.duration_s", "sweep.fixed_angle_deg"],
        },
        "sweeps": [build_sweep_index(s, manifest_path) for s in sweeps],
    }
    return json_safe(index)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build a StormDeck engine-facing volume index from a case-probe manifest.")
    parser.add_argument("manifest", help="Path to manifest.json produced by scripts/stormdeck_case_probe.py")
    parser.add_argument("--out", help="Output JSON path; defaults to stormdeck_volume_index.json next to manifest")
    args = parser.parse_args(argv)

    manifest_path = Path(args.manifest).expanduser().resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    index = build_volume_index(manifest, manifest_path=manifest_path)

    out_path = Path(args.out).expanduser().resolve() if args.out else manifest_path.parent / "stormdeck_volume_index.json"
    out_path.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
