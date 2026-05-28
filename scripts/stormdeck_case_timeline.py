#!/usr/bin/env python3
"""Build a case-level StormDeck timeline from CfRadial inventory metadata.

This script is intentionally metadata-first. It can consume the lightweight JSON
inventory pasted back from wea-fs, or scan a glob of local CfRadial files when
netCDF4 is available. It does not copy radar data into git or into the timeline.
"""

from __future__ import annotations

import argparse
import glob
import json
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


TIME_FORMATS = ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%SZ")


def parse_time(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    for fmt in TIME_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass
    return None


def seconds_between(a: Optional[str], b: Optional[str]) -> Optional[float]:
    ta = parse_time(a)
    tb = parse_time(b)
    if ta is None or tb is None:
        return None
    return round((tb - ta).total_seconds(), 3)


def median_or_none(values: Iterable[float]) -> Optional[float]:
    vals = list(values)
    if not vals:
        return None
    return round(float(statistics.median(vals)), 3)


def sort_files(files: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(files, key=lambda f: parse_time(f.get("start_time") or f.get("time_coverage_start")) or datetime.min)


def clean_sweeps(sweeps: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [s for s in sweeps if "note" not in s]


def volume_modes(file_row: Dict[str, Any]) -> List[str]:
    modes = []
    for sweep in clean_sweeps(file_row.get("sweeps") or []):
        mode = sweep.get("sweep_mode")
        if mode is not None:
            modes.append(str(mode))
    return sorted(set(modes))


def timeline_fixed_angle(sweep: Dict[str, Any]) -> Dict[str, Any]:
    """Return the fixed angle StormDeck should expose for timeline grouping.

    Cf/Radial group-level ``sweep_fixed_angle`` can be misleading for KATD RHI
    groups: observed samples report 0.5 degrees there while the actual fixed
    coordinate is azimuth. Prefer coordinate-derived metadata when present.
    """
    if sweep.get("fixed_angle_deg") is not None:
        return {
            "type": sweep.get("fixed_angle_type") or "derived",
            "deg": round(float(sweep["fixed_angle_deg"]), 6),
            "source": "coordinate_derived",
        }
    if sweep.get("sweep_fixed_angle") is not None:
        mode = str(sweep.get("sweep_mode") or "").lower()
        if mode == "rhi":
            return {
                "type": "azimuth_missing",
                "deg": None,
                "source": "group_sweep_fixed_angle_not_trusted_for_rhi",
            }
        return {
            "type": "elevation",
            "deg": round(float(sweep["sweep_fixed_angle"]), 6),
            "source": "group_sweep_fixed_angle",
        }
    return {"type": "unknown", "deg": None, "source": "missing"}


def compact_volume(file_row: Dict[str, Any], idx: int) -> Dict[str, Any]:
    sweeps = clean_sweeps(file_row.get("sweeps") or [])
    start = file_row.get("start_time") or file_row.get("time_coverage_start")
    end = file_row.get("end_time") or file_row.get("time_coverage_end")
    fixed_angles = []
    fixed_angle_types = []
    gate_counts = []
    ray_counts = []
    modes = []
    for sweep in sweeps:
        fixed = timeline_fixed_angle(sweep)
        if fixed["deg"] is not None:
            fixed_angles.append(fixed["deg"])
        if fixed["type"] != "unknown":
            fixed_angle_types.append(fixed["type"])
        dims = sweep.get("dims") or {}
        if dims.get("range") is not None:
            gate_counts.append(int(dims["range"]))
        if dims.get("time") is not None:
            ray_counts.append(int(dims["time"]))
        if sweep.get("sweep_mode") is not None:
            modes.append(str(sweep["sweep_mode"]))
    return {
        "ordinal": idx,
        "file": file_row.get("file"),
        "size_mb": file_row.get("size_mb"),
        "scan_name": file_row.get("scan_name"),
        "start_time": start,
        "end_time": end,
        "duration_s": seconds_between(start, end),
        "sweep_count": file_row.get("sweep_count") or len(sweeps),
        "scan_modes": sorted(set(modes)),
        "fixed_angle_type": sorted(set(fixed_angle_types))[0] if len(set(fixed_angle_types)) == 1 else "mixed_or_unknown",
        "fixed_angles_sample": fixed_angles[:8],
        "ray_count_values_sample": sorted(set(ray_counts))[:8],
        "gate_count_values_sample": sorted(set(gate_counts), reverse=True)[:8],
    }


def longest_repeating_prefix(names: List[str], max_len: int = 12) -> List[str]:
    if not names:
        return []
    best = names[:1]
    upper = min(max_len, len(names))
    for n in range(1, upper + 1):
        pattern = names[:n]
        ok = True
        for i, name in enumerate(names):
            if name != pattern[i % n]:
                ok = False
                break
        if ok:
            return pattern
        # For partial samples like A B C A B C A, accept the shortest prefix
        # once it covers at least two full cycles plus a partial repeat.
        if len(names) >= n * 2 and all(name == pattern[i % n] for i, name in enumerate(names[: n * 2])):
            best = pattern
    return best


def build_scan_summaries(files: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in files:
        grouped[str(row.get("scan_name") or "unknown")].append(row)

    summaries: Dict[str, Dict[str, Any]] = {}
    for scan_name, rows in sorted(grouped.items()):
        rows = sort_files(rows)
        starts = [r.get("start_time") or r.get("time_coverage_start") for r in rows]
        start_spacings = [seconds_between(a, b) for a, b in zip(starts, starts[1:])]
        start_spacings_f = [x for x in start_spacings if x is not None]
        durations = [seconds_between(r.get("start_time") or r.get("time_coverage_start"), r.get("end_time") or r.get("time_coverage_end")) for r in rows]
        durations_f = [x for x in durations if x is not None]
        sweep_counts = sorted(set(int(r.get("sweep_count") or 0) for r in rows))
        modes = sorted(set(m for r in rows for m in volume_modes(r)))
        gate_counts = set()
        ray_counts = set()
        fixed_angles = set()
        fixed_angle_types = set()
        for row in rows:
            for sweep in clean_sweeps(row.get("sweeps") or []):
                dims = sweep.get("dims") or {}
                if dims.get("range") is not None:
                    gate_counts.add(int(dims["range"]))
                if dims.get("time") is not None:
                    ray_counts.add(int(dims["time"]))
                fixed = timeline_fixed_angle(sweep)
                if fixed["deg"] is not None:
                    fixed_angles.add(fixed["deg"])
                if fixed["type"] != "unknown":
                    fixed_angle_types.add(fixed["type"])
        size_values = sorted(float(r["size_mb"]) for r in rows if r.get("size_mb") is not None)
        summaries[scan_name] = {
            "count": len(rows),
            "scan_modes": modes,
            "sweep_count_values": sweep_counts,
            "median_duration_s": median_or_none(durations_f),
            "median_start_spacing_s": median_or_none(start_spacings_f),
            "size_mb_values_sample": sorted(set(size_values))[:8],
            "fixed_angles_sample": sorted(fixed_angles)[:12],
            "fixed_angle_type_values": sorted(fixed_angle_types),
            "ray_count_values_sample": sorted(ray_counts, reverse=True)[:12],
            "gate_count_values_sample": sorted(gate_counts, reverse=True)[:12],
        }
    return summaries


def build_case_timeline(inventory: Dict[str, Any], case_id: Optional[str] = None) -> Dict[str, Any]:
    files = sort_files([f for f in inventory.get("files", []) if not f.get("error")])
    compact = [compact_volume(row, idx) for idx, row in enumerate(files)]
    starts = [v.get("start_time") for v in compact]
    all_start_spacings = [seconds_between(a, b) for a, b in zip(starts, starts[1:])]
    all_start_spacings_f = [x for x in all_start_spacings if x is not None]
    scan_names = [str(v.get("scan_name") or "unknown") for v in compact]
    scan_mode_counter = Counter(m for v in compact for m in v.get("scan_modes", []))
    has_sector = any(m in ("sector", "ppi") for m in scan_mode_counter)
    has_rhi = "rhi" in scan_mode_counter
    warnings = []
    if has_sector and has_rhi:
        warnings.append("Mixed PPI/sector and RHI scans detected; timeline should group by scan_name and scan_mode before temporal comparisons.")
    if len(set(scan_names)) > 1:
        warnings.append("Multiple scan strategies are interleaved; do not compare adjacent files as equivalent volumes without matching scan_name and fixed angle.")

    timeline = {
        "schema": "stormdeck.case_timeline.v0",
        "case_id": case_id or Path(str(inventory.get("root") or "case")).name,
        "source_root": inventory.get("root"),
        "volume_count": len(compact),
        "case_start_time": compact[0].get("start_time") if compact else None,
        "case_end_time": compact[-1].get("end_time") if compact else None,
        "median_volume_start_spacing_s": median_or_none(all_start_spacings_f),
        "scan_name_counts": dict(sorted(Counter(scan_names).items())),
        "scan_mode_counts": dict(sorted(scan_mode_counter.items())),
        "playlist_pattern_sample": longest_repeating_prefix(scan_names),
        "scan_summaries": build_scan_summaries(files),
        "engine_hints": {
            "contains_mixed_scan_strategies": len(set(scan_names)) > 1 or (has_sector and has_rhi),
            "contains_rhi": has_rhi,
            "contains_sector_or_ppi": has_sector,
            "timeline_should_group_by_scan_name": len(set(scan_names)) > 1,
            "temporal_deltas_require_matching_scan_name": True,
            "temporal_deltas_require_matching_fixed_angle": True,
        },
        "warnings": warnings,
        "volumes": compact,
    }
    return timeline


def scalar_var(group: Any, name: str) -> Optional[Any]:
    if name not in group.variables:
        return None
    value = group.variables[name][()]
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def derived_fixed_angle_from_coords(group: Any, sweep_mode: Optional[str]) -> Dict[str, Any]:
    import numpy as np  # type: ignore

    mode = str(sweep_mode or "").lower()
    coord_name = "azimuth" if mode == "rhi" else "elevation"
    if coord_name not in group.variables:
        return {"fixed_angle_type": None, "fixed_angle_deg": None}
    vals = np.asarray(group.variables[coord_name][:], dtype="float64")
    finite = vals[np.isfinite(vals)]
    if not finite.size:
        return {"fixed_angle_type": None, "fixed_angle_deg": None}
    return {"fixed_angle_type": coord_name, "fixed_angle_deg": float(np.nanmean(finite))}


def scan_cfradial_files(pattern: str, limit: Optional[int] = None) -> Dict[str, Any]:
    from netCDF4 import Dataset  # type: ignore

    paths = sorted(Path(p) for p in glob.glob(pattern))
    if limit:
        paths = paths[:limit]
    rows = []
    for p in paths:
        ds = Dataset(str(p), "r")
        try:
            sweeps = []
            for gname in sorted([g for g in ds.groups if g.startswith("sweep_")], key=lambda s: int(s.split("_", 1)[1]) if s.split("_", 1)[1].isdigit() else s):
                g = ds.groups[gname]
                sweep_mode = scalar_var(g, "sweep_mode")
                fixed = derived_fixed_angle_from_coords(g, sweep_mode if isinstance(sweep_mode, str) else None)
                sweeps.append({
                    "name": gname,
                    "dims": {k: len(v) for k, v in g.dimensions.items()},
                    "sweep_mode": sweep_mode,
                    "sweep_fixed_angle": scalar_var(g, "sweep_fixed_angle"),
                    "fixed_angle_type": fixed["fixed_angle_type"],
                    "fixed_angle_deg": fixed["fixed_angle_deg"],
                    "variables": list(g.variables.keys()),
                })
            rows.append({
                "file": str(p),
                "size_mb": round(p.stat().st_size / 1024 / 1024, 2),
                "data_model": getattr(ds, "data_model", None),
                "instrument_name": getattr(ds, "instrument_name", None),
                "site_name": getattr(ds, "site_name", None),
                "scan_name": getattr(ds, "scan_name", None),
                "start_time": getattr(ds, "start_time", None),
                "end_time": getattr(ds, "end_time", None),
                "time_coverage_start": getattr(ds, "time_coverage_start", None),
                "time_coverage_end": getattr(ds, "time_coverage_end", None),
                "sweep_count": len(sweeps),
                "sweeps": sweeps,
            })
        finally:
            ds.close()
    return {"root": str(Path(pattern).parent), "file_count_sampled": len(rows), "files": rows}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build a StormDeck case timeline from an inventory JSON or CfRadial glob.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--inventory", help="Path to inventory JSON from a metadata scan")
    source.add_argument("--glob", help="Quoted glob for CfRadial files, for example '/case/*.nc'")
    parser.add_argument("--limit", type=int, help="Limit file count when using --glob")
    parser.add_argument("--case-id", help="Case identifier to write into the timeline")
    parser.add_argument("--out", help="Output JSON path; default prints to stdout")
    args = parser.parse_args(argv)

    if args.inventory:
        inventory = json.loads(Path(args.inventory).read_text(encoding="utf-8"))
    else:
        inventory = scan_cfradial_files(args.glob, args.limit)
    timeline = build_case_timeline(inventory, args.case_id)
    text = json.dumps(timeline, indent=2, sort_keys=True) + "\n"
    if args.out:
        output_path = Path(args.out).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
