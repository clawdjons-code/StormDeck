#!/usr/bin/env python3
"""Export native RHI observed-gate vertical slices for StormDeck.

This intentionally exports native RHI sweeps only. It does not derive arbitrary
A-B vertical slices from PPI data, grid volumes, or interpolate unsampled space.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from stormdeck_field_preview import (
    _choose_sweep,
    _json_value_matrix,
    _read_coord,
    _read_scalar_var,
    _require_dataset,
    _sample_axis,
    _site_payload,
    _stride_for,
    canonical_field,
    finite_stats,
    json_safe,
    read_masked_field,
)

VERTICAL_SLICE_WARNING = "Native RHI observed gates only; not arbitrary A-B interpolation, not gridded 3D, and not a vertical retrieval from PPI."


def _span(values: np.ndarray) -> float:
    return float(np.nanmax(values) - np.nanmin(values)) if values.size else 0.0


def is_rhi_like(azimuth_deg: Any, elevation_deg: Any, sweep_mode: Optional[str] = None) -> bool:
    mode = str(sweep_mode or "").lower()
    if "rhi" in mode:
        return True
    az = np.asarray(azimuth_deg, dtype="float64")
    el = np.asarray(elevation_deg, dtype="float64")
    return _span(el) > max(_span(az), 0.25)


def build_vertical_slice_from_arrays(
    *,
    field: Any,
    range_m: Any,
    azimuth_deg: Any,
    elevation_deg: Any,
    field_name: str,
    source_path: str,
    sweep_name: str,
    field_units: Optional[str] = None,
    field_long_name: Optional[str] = None,
    source_schema: Optional[str] = None,
    source_time: Optional[str] = None,
    scan_name: Optional[str] = None,
    sweep_mode: Optional[str] = None,
    radar_latitude_deg: Optional[Any] = None,
    radar_longitude_deg: Optional[Any] = None,
    radar_altitude_m: Optional[Any] = None,
    max_rays: int = 180,
    max_gates: int = 420,
    require_rhi: bool = True,
) -> Dict[str, Any]:
    raw = np.asarray(field, dtype="float64").copy()
    if raw.ndim != 2:
        raise ValueError(f"field must be a 2-D [ray, gate] array; got shape {raw.shape}")
    raw[raw <= -999] = np.nan
    ranges = np.asarray(range_m, dtype="float64")
    az = np.asarray(azimuth_deg, dtype="float64")
    el = np.asarray(elevation_deg, dtype="float64")
    ray_count, gate_count = raw.shape
    if len(az) != ray_count:
        raise ValueError(f"azimuth length {len(az)} does not match field ray count {ray_count}")
    if len(el) != ray_count:
        raise ValueError(f"elevation length {len(el)} does not match field ray count {ray_count}")
    if len(ranges) != gate_count:
        raise ValueError(f"range length {len(ranges)} does not match field gate count {gate_count}")
    if require_rhi and not is_rhi_like(az, el, sweep_mode):
        raise ValueError("vertical slice export requires native RHI-like geometry; PPI-derived A-B interpolation is intentionally not exported")

    ray_stride = _stride_for(ray_count, max_rays)
    gate_stride = _stride_for(gate_count, max_gates)
    sampled = raw[::ray_stride, ::gate_stride]
    sampled_az = _sample_axis(az, ray_stride)
    sampled_el = _sample_axis(el, ray_stride)
    sampled_ranges = _sample_axis(ranges, gate_stride)
    reflectivity_like = field_name.upper() in ("REF", "DBZ", "DZ", "ZH")

    return {
        "schema": "stormdeck.vertical_slice.v0",
        "scientific_status": "observed_native_rhi_gates_not_gridded_not_interpolated",
        "source_schema": source_schema,
        "source": {
            "path": source_path,
            "format": "CfRadial NetCDF native RHI sweep group or equivalent extracted arrays",
            "time_coverage_start": source_time,
            "scan_name": scan_name,
        },
        "site": _site_payload(radar_latitude_deg, radar_longitude_deg, radar_altitude_m),
        "sweep": {
            "name": sweep_name,
            "scan_type": "RHI",
            "fixed_angle_type": "azimuth",
            "fixed_azimuth_deg": json_safe(float(np.nanmedian(az))) if az.size else None,
            "ray_count": int(ray_count),
            "gate_count": int(gate_count),
            "elevation_min_deg": json_safe(float(np.nanmin(el))) if el.size else None,
            "elevation_max_deg": json_safe(float(np.nanmax(el))) if el.size else None,
            "azimuth_min_deg": json_safe(float(np.nanmin(az))) if az.size else None,
            "azimuth_max_deg": json_safe(float(np.nanmax(az))) if az.size else None,
            "range_max_m": json_safe(float(np.nanmax(ranges))) if ranges.size else None,
        },
        "field": {"name": field_name, "units": field_units, "long_name": field_long_name, "stats": finite_stats(raw)},
        "sampling": {
            "max_rays": int(max_rays),
            "max_gates": int(max_gates),
            "ray_stride": int(ray_stride),
            "gate_stride": int(gate_stride),
            "sampled_ray_count": int(sampled.shape[0]),
            "sampled_gate_count": int(sampled.shape[1]),
        },
        "coordinates": {
            "range_m": json_safe(sampled_ranges),
            "elevation_deg": json_safe(sampled_el),
            "azimuth_deg": json_safe(sampled_az),
        },
        "values": _json_value_matrix(sampled),
        "viewer_hints": {
            "default_view": "native_rhi_vertical_slice",
            "horizontal_axis": "range_m",
            "vertical_axis": "elevation_deg",
            "color_table": "atd_reflectivity_dbz" if reflectivity_like else "generic_diverging_or_linear",
            "observed_vs_inferred_label": "observed RHI gates",
        },
        "warnings": [VERTICAL_SLICE_WARNING],
    }


def build_vertical_slice_from_cfradial(
    nc_path: Path,
    *,
    field: str = "REF",
    sweep: Optional[str] = None,
    sweep_index: int = 0,
    max_rays: int = 180,
    max_gates: int = 420,
    require_rhi: bool = True,
) -> Dict[str, Any]:
    Dataset = _require_dataset()
    ds = Dataset(str(nc_path), "r")
    try:
        sweep_name, group = _choose_sweep(ds, sweep, sweep_index)
        field_var_name = canonical_field(group, field)
        if not field_var_name:
            raise SystemExit(f"Field not found: {field}; available={list(group.variables.keys())}")
        _, ranges = _read_coord(group, "range")
        _, az = _read_coord(group, "azimuth")
        _, el = _read_coord(group, "elevation")
        sweep_mode = getattr(group, "sweep_mode", None)
        var = group.variables[field_var_name]
        return build_vertical_slice_from_arrays(
            field=read_masked_field(var),
            range_m=ranges,
            azimuth_deg=az,
            elevation_deg=el,
            field_name=field_var_name,
            field_units=json_safe(getattr(var, "units", None)),
            field_long_name=json_safe(getattr(var, "long_name", None)),
            source_path=str(nc_path),
            source_schema="CfRadial NetCDF",
            source_time=json_safe(getattr(ds, "time_coverage_start", None)),
            scan_name=json_safe(getattr(ds, "scan_name", None)),
            sweep_mode=json_safe(sweep_mode),
            radar_latitude_deg=_read_scalar_var(ds, "latitude"),
            radar_longitude_deg=_read_scalar_var(ds, "longitude"),
            radar_altitude_m=_read_scalar_var(ds, "altitude"),
            sweep_name=sweep_name,
            max_rays=max_rays,
            max_gates=max_gates,
            require_rhi=require_rhi,
        )
    finally:
        ds.close()


def build_vertical_slice_playlist(slices: List[Dict[str, Any]], *, case_id: Optional[str] = None, field: Optional[str] = None, strict_compatible: bool = False) -> Dict[str, Any]:
    frames = []
    times = []
    fixed_azimuths = []
    geometries = []
    scan_names = []
    for index, vertical_slice in enumerate(slices):
        source = vertical_slice.get("source", {})
        sweep = vertical_slice.get("sweep", {})
        sampling = vertical_slice.get("sampling", {})
        if source.get("time_coverage_start"):
            times.append(str(source["time_coverage_start"]))
        if source.get("scan_name"):
            scan_names.append(str(source["scan_name"]))
        if sweep.get("fixed_azimuth_deg") is not None:
            fixed_azimuths.append(round(float(sweep["fixed_azimuth_deg"]), 1))
        geometries.append(f"{sampling.get('sampled_ray_count')}x{sampling.get('sampled_gate_count')}")
        frames.append({
            "frame_index": index,
            "previous_frame_index": index - 1 if index > 0 else None,
            "time_coverage_start": source.get("time_coverage_start"),
            "source_path": source.get("path"),
            "vertical_slice": vertical_slice,
        })
    mixed_reasons = []
    if len(set(scan_names)) > 1:
        mixed_reasons.append("Mixed scan names")
    if len(set(fixed_azimuths)) > 1:
        mixed_reasons.append("Mixed fixed azimuths")
    if len(set(geometries)) > 1:
        mixed_reasons.append("Mixed sampled geometries")
    if strict_compatible and mixed_reasons:
        raise ValueError("; ".join(mixed_reasons))
    return {
        "schema": "stormdeck.vertical_slice_playlist.v0",
        "case_id": case_id,
        "field": field or (slices[0].get("field", {}).get("name") if slices else None),
        "frame_count": len(frames),
        "timeline": {"start_time": times[0] if times else None, "end_time": times[-1] if times else None},
        "frames": frames,
        "compatibility": {
            "status": "mixed_non_comparable" if mixed_reasons else "homogeneous_comparable",
            "scan_names": sorted(set(scan_names)),
            "fixed_azimuths_deg": sorted(set(fixed_azimuths)),
            "sampled_geometries": sorted(set(geometries)),
            "mixed_reasons": mixed_reasons,
            "operator_note": "Playlist uses native RHI observed gates for browsing; no arbitrary A-B interpolation.",
        },
        "warnings": [VERTICAL_SLICE_WARNING],
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Export stormdeck.vertical_slice.v0 or vertical_slice_playlist.v0 from native RHI CfRadial sweeps.")
    parser.add_argument("input", nargs="+", help="Input CfRadial .nc file(s), in frame order")
    parser.add_argument("--out", required=True)
    parser.add_argument("--field", default="REF")
    parser.add_argument("--case-id", default=None)
    parser.add_argument("--playlist", action="store_true")
    parser.add_argument("--sweep", default=None)
    parser.add_argument("--sweep-index", type=int, default=0)
    parser.add_argument("--max-rays", type=int, default=180)
    parser.add_argument("--max-gates", type=int, default=420)
    parser.add_argument("--strict-compatible-playlist", action="store_true")
    args = parser.parse_args(argv)
    slices = [
        build_vertical_slice_from_cfradial(
            Path(path).expanduser().resolve(),
            field=args.field,
            sweep=args.sweep,
            sweep_index=args.sweep_index,
            max_rays=args.max_rays,
            max_gates=args.max_gates,
        )
        for path in args.input
    ]
    payload = build_vertical_slice_playlist(slices, case_id=args.case_id, field=args.field, strict_compatible=args.strict_compatible_playlist) if args.playlist or len(slices) > 1 else slices[0]
    out = Path(args.out).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote vertical slice artifact: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
