#!/usr/bin/env python3
"""Export a browser-safe observed-gate radar field preview from one CfRadial sweep.

This is StormDeck's first radar-array handoff artifact for the replay cockpit. It
samples one native sweep into small JSON arrays that the browser can draw without
copying full raw radar volumes into the repo and without implying gridded 3D.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np


FIELD_ALIASES: Dict[str, List[str]] = {
    "REF": ["REF", "DBZ", "DZ", "ZH", "reflectivity", "corrected_reflectivity"],
    "VEL": ["VEL", "VR", "V", "velocity", "radial_velocity"],
    "SW": ["SW", "WIDTH", "spectrum_width", "spectrum_width_h"],
    "ZDR": ["ZDR", "differential_reflectivity"],
    "RHO": ["RHO", "RHOHV", "RHX", "cross_correlation_ratio"],
    "PHI": ["PHI", "PHIDP", "differential_phase"],
}

COORD_ALIASES: Dict[str, List[str]] = {
    "range": ["range", "gate_range"],
    "azimuth": ["azimuth", "az", "ray_azimuth"],
    "elevation": ["elevation", "el", "ray_elevation"],
    "time": ["time"],
}


VALUE_WARNING = "Observed radar field sample only; not a gridded volume and not a field-value delta."


def json_safe(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return [json_safe(v) for v in value.tolist()]
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    return str(value)


def first_existing_var(group: Any, names: Iterable[str]) -> Optional[str]:
    lower = {name.lower(): name for name in group.variables.keys()}
    for name in names:
        if name in group.variables:
            return name
        if name.lower() in lower:
            return lower[name.lower()]
    return None


def canonical_field(group: Any, requested: str) -> Optional[str]:
    requested = requested.strip()
    if requested in group.variables:
        return requested
    lower = {name.lower(): name for name in group.variables.keys()}
    for canonical, aliases in FIELD_ALIASES.items():
        if requested.upper() == canonical or requested.lower() in [alias.lower() for alias in aliases]:
            return first_existing_var(group, aliases)
    return lower.get(requested.lower())


def read_masked_field(var: Any) -> np.ndarray:
    arr = var[:]
    if np.ma.isMaskedArray(arr):
        out = arr.astype("float64").filled(np.nan)
    else:
        out = np.asarray(arr, dtype="float64")
        fill = getattr(var, "_FillValue", None)
        if fill is not None:
            out[out == fill] = np.nan
    # ATD/KATD moment fields often use -999.0 for censored gates.
    out[out <= -999] = np.nan
    return out


def finite_stats(arr: np.ndarray) -> Dict[str, Any]:
    finite = arr[np.isfinite(arr)]
    stats: Dict[str, Any] = {
        "shape": list(arr.shape),
        "valid_gate_count": int(finite.size),
        "missing_gate_count": int(arr.size - finite.size),
    }
    if finite.size:
        stats.update(
            {
                "min": float(np.nanmin(finite)),
                "max": float(np.nanmax(finite)),
                "mean": float(np.nanmean(finite)),
                "p01": float(np.nanpercentile(finite, 1)),
                "p50": float(np.nanpercentile(finite, 50)),
                "p99": float(np.nanpercentile(finite, 99)),
            }
        )
    return stats


def _stride_for(length: int, max_count: int) -> int:
    max_count = max(1, int(max_count))
    return max(1, int(math.ceil(length / max_count)))


def _sample_axis(axis: np.ndarray, stride: int) -> np.ndarray:
    return np.asarray(axis, dtype="float64")[::stride]


def _json_value_matrix(arr: np.ndarray) -> List[List[Optional[float]]]:
    rows: List[List[Optional[float]]] = []
    for row in arr:
        rows.append([None if not math.isfinite(float(value)) else float(value) for value in row])
    return rows


def _round_tenth(value: float) -> Optional[float]:
    if not math.isfinite(value):
        return None
    scaled = float(value) * 10.0
    epsilon = 1e-6
    if scaled >= 0:
        return math.floor(scaled + 0.5 + epsilon) / 10.0
    return math.ceil(scaled - 0.5 - epsilon) / 10.0


def _angle_label(value: Optional[float], approximate: bool = False) -> Optional[str]:
    if value is None:
        return None
    prefix = "~" if approximate else ""
    return f"{prefix}{value:.1f}°"


def _site_payload(latitude: Optional[Any], longitude: Optional[Any], altitude: Optional[Any]) -> Dict[str, Any]:
    lat = json_safe(float(latitude)) if latitude is not None and math.isfinite(float(latitude)) else None
    lon = json_safe(float(longitude)) if longitude is not None and math.isfinite(float(longitude)) else None
    alt = json_safe(float(altitude)) if altitude is not None and math.isfinite(float(altitude)) else None
    return {
        "latitude_deg": lat,
        "longitude_deg": lon,
        "altitude_m": alt,
        "source": "CfRadial site metadata" if lat is not None and lon is not None else "not_available",
    }


def _sector_outline_payload(az: np.ndarray, ranges: np.ndarray, site: Dict[str, Any]) -> Dict[str, Any]:
    max_range = float(np.nanmax(ranges)) if ranges.size else None
    if site.get("latitude_deg") is None or site.get("longitude_deg") is None or max_range is None:
        return {
            "status": "not_georeferenced_no_site_location",
            "rendering_mode": "sector_outline_only_not_gridded",
            "sector_outline": None,
        }
    return {
        "status": "georeferenced_sector_outline_available",
        "rendering_mode": "sector_outline_only_not_gridded",
        "sector_outline": {
            "azimuth_min_deg": json_safe(float(np.nanmin(az))) if az.size else None,
            "azimuth_max_deg": json_safe(float(np.nanmax(az))) if az.size else None,
            "range_max_m": json_safe(max_range),
            "projection_note": "Browser preview draws a radar-centered sector outline; no gate gridding or map reprojection is applied.",
        },
    }


def build_field_preview_from_arrays(
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
    radar_latitude_deg: Optional[Any] = None,
    radar_longitude_deg: Optional[Any] = None,
    radar_altitude_m: Optional[Any] = None,
    max_rays: int = 240,
    max_gates: int = 480,
) -> Dict[str, Any]:
    """Build the stable browser-facing field-preview JSON contract."""
    raw = np.asarray(field, dtype="float64")
    if raw.ndim != 2:
        raise ValueError(f"field must be a 2-D [ray, gate] array; got shape {raw.shape}")
    raw = raw.copy()
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

    ray_stride = _stride_for(ray_count, max_rays)
    gate_stride = _stride_for(gate_count, max_gates)
    sampled = raw[::ray_stride, ::gate_stride]
    sampled_az = _sample_axis(az, ray_stride)
    sampled_el = _sample_axis(el, ray_stride)
    sampled_ranges = _sample_axis(ranges, gate_stride)
    el_span = float(np.nanmax(el) - np.nanmin(el)) if el.size else float("nan")
    az_span = float(np.nanmax(az) - np.nanmin(az)) if az.size else float("nan")
    elevation_min = _round_tenth(float(np.nanmin(el))) if el.size else None
    elevation_max = _round_tenth(float(np.nanmax(el))) if el.size else None
    elevation_median = _round_tenth(float(np.nanmedian(el))) if el.size else None
    azimuth_min = _round_tenth(float(np.nanmin(az))) if az.size else None
    azimuth_max = _round_tenth(float(np.nanmax(az))) if az.size else None
    azimuth_median = _round_tenth(float(np.nanmedian(az))) if az.size else None
    use_elevation_label = (elevation_median is not None) and (not math.isfinite(az_span) or not math.isfinite(el_span) or az_span >= el_span)
    fixed_angle = elevation_median if use_elevation_label else azimuth_median
    fixed_angle_approx = use_elevation_label and elevation_min is not None and elevation_max is not None and elevation_min != elevation_max
    fixed_angle_label = _angle_label(fixed_angle, fixed_angle_approx)
    reflectivity_like = field_name.upper() in ("REF", "DBZ", "DZ", "ZH")
    site = _site_payload(radar_latitude_deg, radar_longitude_deg, radar_altitude_m)
    map_context = _sector_outline_payload(az, ranges, site)

    return {
        "schema": "stormdeck.field_preview.v0",
        "source_schema": source_schema,
        "scientific_status": "observed_native_gates_not_gridded_not_interpolated",
        "source": {
            "path": source_path,
            "format": "CfRadial NetCDF sweep group or equivalent extracted arrays",
            "time_coverage_start": source_time,
            "scan_name": scan_name,
        },
        "site": site,
        "map_context": map_context,
        "display_metadata": {
            "scan_name": scan_name,
            "time_coverage_start": source_time,
            "radial_count": int(ray_count),
            "fixed_angle_label": fixed_angle_label,
            "elevation_precision_deg": 0.1,
            "elevation_min_deg": elevation_min,
            "elevation_max_deg": elevation_max,
            "elevation_median_deg": elevation_median,
            "azimuth_min_deg": azimuth_min,
            "azimuth_max_deg": azimuth_max,
            "azimuth_median_deg": azimuth_median,
            "azimuth_span_deg": json_safe(az_span),
            "elevation_span_deg": json_safe(el_span),
        },
        "sweep": {
            "name": sweep_name,
            "ray_count": int(ray_count),
            "gate_count": int(gate_count),
            "azimuth_min_deg": json_safe(float(np.nanmin(az))) if az.size else None,
            "azimuth_max_deg": json_safe(float(np.nanmax(az))) if az.size else None,
            "elevation_min_deg": json_safe(float(np.nanmin(el))) if el.size else None,
            "elevation_max_deg": json_safe(float(np.nanmax(el))) if el.size else None,
        },
        "field": {
            "name": field_name,
            "units": field_units,
            "long_name": field_long_name,
            "stats": finite_stats(raw),
        },
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
            "azimuth_deg": json_safe(sampled_az),
            "elevation_deg": json_safe(sampled_el),
        },
        "values": _json_value_matrix(sampled),
        "viewer_hints": {
            "default_view": "native_polar_sweep",
            "color_table": "atd_reflectivity_dbz" if reflectivity_like else "generic_diverging_or_linear",
            "observed_vs_inferred_label": "observed gates",
        },
        "warnings": [VALUE_WARNING],
    }


def _require_dataset() -> Any:
    try:
        from netCDF4 import Dataset  # type: ignore
    except Exception as exc:  # pragma: no cover - depends on target host
        raise SystemExit("Missing netCDF4. On wea-fs use python3 with python3-netcdf4 installed.") from exc
    return Dataset


def _choose_sweep(ds: Any, sweep_name: Optional[str], sweep_index: int) -> Tuple[str, Any]:
    if sweep_name:
        if sweep_name not in ds.groups:
            raise SystemExit(f"Sweep group not found: {sweep_name}")
        return sweep_name, ds.groups[sweep_name]
    sweeps = sorted((name, group) for name, group in ds.groups.items() if name.startswith("sweep_"))
    if not sweeps:
        raise SystemExit("No sweep_* groups found in CfRadial file.")
    if sweep_index < 0 or sweep_index >= len(sweeps):
        raise SystemExit(f"Sweep index {sweep_index} out of range; available 0..{len(sweeps)-1}")
    return sweeps[sweep_index]


def _read_coord(group: Any, logical_name: str) -> Tuple[str, np.ndarray]:
    name = first_existing_var(group, COORD_ALIASES[logical_name])
    if not name:
        raise SystemExit(f"Required coordinate missing: {logical_name}")
    return name, np.asarray(group.variables[name][:], dtype="float64")


def _read_scalar_var(ds: Any, name: str) -> Optional[Any]:
    var = ds.variables.get(name)
    if var is None:
        return None
    arr = np.asarray(var[:])
    if arr.size == 0:
        return None
    return arr.reshape(-1)[0].item()


def build_field_preview_from_cfradial(
    nc_path: Path,
    *,
    field: str = "REF",
    sweep: Optional[str] = None,
    sweep_index: int = 0,
    max_rays: int = 240,
    max_gates: int = 480,
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
        var = group.variables[field_var_name]
        return build_field_preview_from_arrays(
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
            radar_latitude_deg=_read_scalar_var(ds, "latitude"),
            radar_longitude_deg=_read_scalar_var(ds, "longitude"),
            radar_altitude_m=_read_scalar_var(ds, "altitude"),
            sweep_name=sweep_name,
            max_rays=max_rays,
            max_gates=max_gates,
        )
    finally:
        ds.close()


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Export stormdeck.field_preview.v0 JSON from one CfRadial sweep.")
    parser.add_argument("input", help="Input CfRadial .nc file")
    parser.add_argument("--out", required=True, help="Output field_preview.json path")
    parser.add_argument("--field", default="REF", help="Field alias or variable name, e.g. REF, DBZ, VEL")
    parser.add_argument("--sweep", default=None, help="Sweep group name, e.g. sweep_0")
    parser.add_argument("--sweep-index", type=int, default=0, help="Sweep index if --sweep is omitted")
    parser.add_argument("--max-rays", type=int, default=240, help="Maximum sampled rays in browser JSON")
    parser.add_argument("--max-gates", type=int, default=480, help="Maximum sampled gates in browser JSON")
    args = parser.parse_args(argv)

    preview = build_field_preview_from_cfradial(
        Path(args.input).expanduser().resolve(),
        field=args.field,
        sweep=args.sweep,
        sweep_index=args.sweep_index,
        max_rays=args.max_rays,
        max_gates=args.max_gates,
    )
    out = Path(args.out).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(preview, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote field preview: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
