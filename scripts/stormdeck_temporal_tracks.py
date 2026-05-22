#!/usr/bin/env python3
"""Build comparable temporal tracks from StormDeck CfRadial inventory metadata.

This exporter is stricter than the case timeline. It classifies complete scan
products separately from tiny transition fragments, then groups only comparable
observations into tracks suitable for replay and future "what changed" panels.
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

TIME_FORMATS = ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%SZ")

EXPECTED_SWEEP_COUNTS = {
    "QLCS_LDR_0.5Only": 1,
    "Supercell_Fast_Deg_Staggered_Test": 20,
    "RHI_LDR_Narrow_Sector": 9,
}

CLASS_BY_SCAN = {
    "QLCS_LDR_0.5Only": "complete_low_level_sector",
    "Supercell_Fast_Deg_Staggered_Test": "complete_supercell_3d",
    "RHI_LDR_Narrow_Sector": "complete_native_rhi",
}


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


def scan_modes(row: Dict[str, Any]) -> List[str]:
    modes = []
    for sweep in clean_sweeps(row.get("sweeps") or []):
        mode = sweep.get("sweep_mode")
        if mode is not None:
            modes.append(str(mode))
    return sorted(set(modes))


def rounded_angle(value: Any) -> Optional[float]:
    if value is None:
        return None
    return round(float(value), 1)


def classify_volume(row: Dict[str, Any]) -> Tuple[str, str]:
    scan_name = str(row.get("scan_name") or "unknown")
    sweep_count = int(row.get("sweep_count") or len(clean_sweeps(row.get("sweeps") or [])))
    size_mb = float(row.get("size_mb") or 0.0)
    modes = scan_modes(row)

    reasons: List[str] = []
    if size_mb < 1.0:
        reasons.append("size_below_1mb")
    expected = EXPECTED_SWEEP_COUNTS.get(scan_name)
    if expected is not None and sweep_count != expected:
        reasons.append(f"sweep_count_{sweep_count}_expected_{expected}")
    if len(modes) > 1:
        reasons.append("mixed_scan_modes")

    if reasons:
        return "fragment_or_transition", ";".join(reasons)
    return CLASS_BY_SCAN.get(scan_name, "complete_unknown_scan"), "complete"


def compact_volume(row: Dict[str, Any], ordinal: int, classification: str, reason: str) -> Dict[str, Any]:
    start = row.get("start_time") or row.get("time_coverage_start")
    end = row.get("end_time") or row.get("time_coverage_end")
    return {
        "ordinal": ordinal,
        "file": row.get("file"),
        "scan_name": row.get("scan_name"),
        "start_time": start,
        "end_time": end,
        "duration_s": seconds_between(start, end),
        "size_mb": row.get("size_mb"),
        "sweep_count": row.get("sweep_count") or len(clean_sweeps(row.get("sweeps") or [])),
        "scan_modes": scan_modes(row),
        "classification": classification,
        "reason": reason,
    }


def fields_for_sweep(sweep: Dict[str, Any]) -> List[str]:
    variables = sweep.get("variables") or []
    excluded = {"time", "range", "azimuth", "elevation", "sweep_mode", "sweep_fixed_angle"}
    return sorted(str(v) for v in variables if str(v) not in excluded)


def track_entries_for_volume(row: Dict[str, Any], compact: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any]]]:
    scan_name = str(row.get("scan_name") or "unknown")
    modes = scan_modes(row)
    sweeps = clean_sweeps(row.get("sweeps") or [])
    entries: List[Tuple[str, Dict[str, Any]]] = []

    if scan_name == "RHI_LDR_Narrow_Sector" and "rhi" in modes:
        track_id = "RHI_LDR_Narrow_Sector__native_rhi__complete"
        entries.append((track_id, {
            "track_id": track_id,
            "scan_name": scan_name,
            "scan_mode": "rhi",
            "track_kind": "native_rhi",
            "fixed_angle_deg": None,
            "native_rhi": True,
            "volumes": [],
        }))
        return entries

    seen_angles = set()
    for sweep in sweeps:
        mode = sweep.get("sweep_mode")
        angle = rounded_angle(sweep.get("sweep_fixed_angle"))
        if mode is None or angle is None:
            continue
        key = (str(mode), angle)
        if key in seen_angles:
            continue
        seen_angles.add(key)
        angle_label = f"{angle:g}deg"
        track_id = f"{scan_name}__{mode}__{angle_label}__complete"
        dims = sweep.get("dims") or {}
        entries.append((track_id, {
            "track_id": track_id,
            "scan_name": scan_name,
            "scan_mode": str(mode),
            "track_kind": "fixed_angle_sweep",
            "fixed_angle_deg": angle,
            "native_rhi": False,
            "gate_count": dims.get("range"),
            "ray_count": dims.get("time"),
            "fields": fields_for_sweep(sweep),
            "volumes": [],
        }))
    return entries


def summarize_track(track: Dict[str, Any]) -> Dict[str, Any]:
    volumes = sorted(track["volumes"], key=lambda v: parse_time(v.get("start_time")) or datetime.min)
    starts = [v.get("start_time") for v in volumes]
    spacings = [seconds_between(a, b) for a, b in zip(starts, starts[1:])]
    spacings_f = [s for s in spacings if s is not None]
    out = {k: v for k, v in track.items() if k != "volumes"}
    out["volume_count"] = len(volumes)
    out["case_start_time"] = volumes[0].get("start_time") if volumes else None
    out["case_end_time"] = volumes[-1].get("end_time") if volumes else None
    out["median_spacing_s"] = median_or_none(spacings_f)
    out["volumes"] = volumes
    return out


def build_temporal_tracks(inventory: Dict[str, Any], case_id: Optional[str] = None) -> Dict[str, Any]:
    files = sort_files([f for f in inventory.get("files", []) if not f.get("error")])
    classification_counter: Counter[str] = Counter()
    quarantine: List[Dict[str, Any]] = []
    track_map: Dict[str, Dict[str, Any]] = {}
    complete_count = 0

    for ordinal, row in enumerate(files):
        classification, reason = classify_volume(row)
        classification_counter[classification] += 1
        compact = compact_volume(row, ordinal, classification, reason)
        if classification == "fragment_or_transition":
            quarantine.append(compact)
            continue
        complete_count += 1
        for track_id, template in track_entries_for_volume(row, compact):
            if track_id not in track_map:
                track_map[track_id] = template
            track_map[track_id]["volumes"].append({
                "ordinal": compact["ordinal"],
                "file": compact["file"],
                "start_time": compact["start_time"],
                "end_time": compact["end_time"],
                "duration_s": compact["duration_s"],
            })

    tracks = [summarize_track(t) for _, t in sorted(track_map.items())]
    warnings = [
        "Temporal deltas must compare only complete volumes within the same track.",
        "Quarantined fragments are transition products and should be hidden from operational replay by default.",
    ]
    return {
        "schema": "stormdeck.temporal_tracks.v0",
        "case_id": case_id or Path(str(inventory.get("root") or "case")).name,
        "source_root": inventory.get("root"),
        "volume_counts": {
            "total": len(files),
            "complete": complete_count,
            "quarantined": len(quarantine),
        },
        "classification_counts": dict(sorted(classification_counter.items())),
        "pairing_rules": {
            "match_track_id": True,
            "match_scan_name": True,
            "match_scan_mode": True,
            "match_fixed_angle_deg_tolerance": 0.05,
            "exclude_quarantined": True,
        },
        "tracks": tracks,
        "quarantine": quarantine,
        "warnings": warnings,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build StormDeck comparable temporal tracks from metadata inventory JSON.")
    parser.add_argument("--inventory", required=True, help="Path to full per-file inventory JSON, for example 217-volumes.txt")
    parser.add_argument("--case-id", help="Case identifier to write into the track index")
    parser.add_argument("--out", help="Output JSON path; default prints to stdout")
    args = parser.parse_args(argv)

    inventory = json.loads(Path(args.inventory).read_text(encoding="utf-8"))
    tracks = build_temporal_tracks(inventory, args.case_id)
    text = json.dumps(tracks, indent=2, sort_keys=True) + "\n"
    if args.out:
        output_path = Path(args.out).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
