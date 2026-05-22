#!/usr/bin/env python3
"""Build metadata-safe StormDeck change summaries from temporal tracks.

This script does not read radar fields or compute reflectivity/velocity deltas.
It summarizes safe replay comparisons inside each temporal track so the viewer
can answer "what changed" without comparing unlike scan products.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

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


def sort_by_start(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(rows, key=lambda r: parse_time(r.get("start_time")) or datetime.min)


def event_between(event: Dict[str, Any], start: Optional[str], end: Optional[str]) -> bool:
    t = parse_time(event.get("start_time"))
    a = parse_time(start)
    b = parse_time(end)
    if t is None or a is None or b is None:
        return False
    return a <= t <= b


def cadence_status(elapsed_s: Optional[float], median_spacing_s: Optional[float]) -> str:
    if elapsed_s is None or median_spacing_s is None:
        return "unknown"
    tolerance = max(5.0, median_spacing_s * 0.10)
    if abs(elapsed_s - median_spacing_s) <= tolerance:
        return "on_cadence"
    if elapsed_s > median_spacing_s + tolerance:
        return "late_or_missing_frame"
    return "early_or_irregular"


def summarize_track_change(track: Dict[str, Any], quarantine: List[Dict[str, Any]]) -> Dict[str, Any]:
    volumes = sort_by_start(track.get("volumes") or [])
    base = {
        "track_id": track.get("track_id"),
        "scan_name": track.get("scan_name"),
        "scan_mode": track.get("scan_mode"),
        "track_kind": track.get("track_kind"),
        "fixed_angle_deg": track.get("fixed_angle_deg"),
        "native_rhi": bool(track.get("native_rhi")),
        "complete_volume_count": len(volumes),
    }
    if len(volumes) < 2:
        return {
            **base,
            "comparison_available": False,
            "reason": "fewer_than_2_complete_volumes",
            "operator_message": "No same-track comparison available yet.",
        }

    previous = volumes[-2]
    latest = volumes[-1]
    elapsed = seconds_between(previous.get("start_time"), latest.get("start_time"))
    nearby_quarantine = [
        q for q in quarantine
        if event_between(q, previous.get("end_time") or previous.get("start_time"), latest.get("start_time"))
    ]
    return {
        **base,
        "comparison_available": True,
        "from_ordinal": previous.get("ordinal"),
        "to_ordinal": latest.get("ordinal"),
        "from_file": previous.get("file"),
        "to_file": latest.get("file"),
        "from_start_time": previous.get("start_time"),
        "to_start_time": latest.get("start_time"),
        "elapsed_s": elapsed,
        "expected_spacing_s": track.get("median_spacing_s"),
        "cadence_status": cadence_status(elapsed, track.get("median_spacing_s")),
        "quarantine_events_between": len(nearby_quarantine),
        "quarantine_event_reasons": sorted({str(q.get("reason")) for q in nearby_quarantine}),
        "operator_message": "Metadata-safe comparison only; radar field deltas not computed.",
    }


def build_change_summary(temporal_tracks: Dict[str, Any]) -> Dict[str, Any]:
    tracks = temporal_tracks.get("tracks") or []
    quarantine = temporal_tracks.get("quarantine") or []
    changes = [summarize_track_change(track, quarantine) for track in tracks]
    comparisons = [c for c in changes if c.get("comparison_available")]
    no_comparisons = [c for c in changes if not c.get("comparison_available")]
    warnings = [
        "This summary is metadata-safe only; it does not include radar field-value deltas.",
        "Every comparison is constrained to complete volumes inside a single temporal track.",
    ]
    if quarantine:
        warnings.append("Quarantined fragments were excluded from comparisons but counted near comparison windows.")

    return {
        "schema": "stormdeck.change_summary.v0",
        "case_id": temporal_tracks.get("case_id"),
        "source_schema": temporal_tracks.get("schema"),
        "source_root": temporal_tracks.get("source_root"),
        "pairing_rules": temporal_tracks.get("pairing_rules", {}),
        "summary_counts": {
            "tracks_total": len(tracks),
            "track_comparisons": len(comparisons),
            "tracks_without_comparison": len(no_comparisons),
            "quarantine_events": len(quarantine),
        },
        "engine_hints": {
            "compare_only_within_track": True,
            "exclude_quarantined": True,
            "field_value_deltas_included": False,
            "safe_for_replay_metadata_panel": True,
        },
        "track_changes": changes,
        "quarantine_summary": {
            "count": len(quarantine),
            "events": quarantine,
        },
        "warnings": warnings,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build metadata-safe StormDeck change summaries from temporal_tracks.json.")
    parser.add_argument("--temporal-tracks", required=True, help="Path to stormdeck.temporal_tracks.v0 JSON")
    parser.add_argument("--out", help="Output JSON path; default prints to stdout")
    args = parser.parse_args(argv)

    temporal_tracks = json.loads(Path(args.temporal_tracks).read_text(encoding="utf-8"))
    summary = build_change_summary(temporal_tracks)
    text = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    if args.out:
        output_path = Path(args.out).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
