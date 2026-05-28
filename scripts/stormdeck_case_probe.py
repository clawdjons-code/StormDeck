#!/usr/bin/env python3
"""StormDeck multi-sweep CfRadial case probe and quicklook exporter.

Reads ATD/KATD CfRadial NetCDF-4 files with sweep_* groups, classifies native
sector PPI and native RHI geometry from coordinate arrays, writes a manifest,
and exports simple observed-data quicklooks for REF, VEL, and SW.

Design constraints captured from ATD data reconnaissance:
- derive geometry from azimuth, elevation, range, and time arrays first;
- do not trust group-level sweep_fixed_angle for RHI fixed azimuth;
- allow each sweep to have its own range axis and gate count;
- reserve manifest fields for future ADT ragged radial support.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

from stormdeck_radar_arrays import masked_numeric_array

# netCDF4 and Pillow are imported lazily so geometry unit tests can run in
# lightweight environments. The operational target, wea-fs, has these packages.
Dataset = None  # type: ignore
Image = None  # type: ignore
ImageDraw = None  # type: ignore


def require_dataset_dep() -> Any:
    global Dataset
    if Dataset is None:
        from netCDF4 import Dataset as _Dataset  # type: ignore
        Dataset = _Dataset
    return Dataset


def require_image_deps() -> Tuple[Any, Any]:
    global Image, ImageDraw
    if Image is None or ImageDraw is None:
        from PIL import Image as _Image, ImageDraw as _ImageDraw  # type: ignore
        Image = _Image
        ImageDraw = _ImageDraw
    return Image, ImageDraw

FIELD_ALIASES: Dict[str, List[str]] = {
    "REF": ["REF", "DBZ", "DZ", "ZH", "reflectivity", "corrected_reflectivity"],
    "VEL": ["VEL", "VR", "V", "velocity", "radial_velocity"],
    "SW": ["SW", "WIDTH", "spectrum_width", "spectrum_width_h"],
}

COORD_ALIASES: Dict[str, List[str]] = {
    "range": ["range", "gate_range"],
    "azimuth": ["azimuth", "az", "ray_azimuth"],
    "elevation": ["elevation", "el", "ray_elevation"],
    "time": ["time"],
    "nyquist_velocity": ["nyquist_velocity", "nyquist", "NYQ"],
}


def json_safe(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, (str, int, float, bool)) or value is None:
        if isinstance(value, float) and not math.isfinite(value):
            return None
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
    for canonical, aliases in FIELD_ALIASES.items():
        if requested.upper() == canonical or requested.lower() in [a.lower() for a in aliases]:
            return first_existing_var(group, aliases)
    return {name.lower(): name for name in group.variables.keys()}.get(requested.lower())


def scalar_var(group: Any, name: str) -> Optional[Any]:
    if name not in group.variables:
        return None
    try:
        value = group.variables[name][()]
        if isinstance(value, np.ndarray) and value.shape == ():
            value = value.item()
        return json_safe(value)
    except Exception:
        return None


def read_float_array(group: Any, logical_name: str) -> Tuple[str, np.ndarray]:
    var_name = first_existing_var(group, COORD_ALIASES[logical_name])
    if not var_name:
        raise ValueError(f"Required coordinate missing: {logical_name}; variables={list(group.variables.keys())}")
    return var_name, np.asarray(group.variables[var_name][:], dtype="float64")


def read_masked_field(var: Any) -> np.ndarray:
    return masked_numeric_array(var)


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


def summarize_angle(values_deg: Sequence[float]) -> Dict[str, Any]:
    arr = np.asarray(values_deg, dtype="float64")
    finite = arr[np.isfinite(arr)]
    if not finite.size:
        return {"min_deg": None, "max_deg": None, "span_deg": None, "mean_deg": None, "varies": False}
    amin = float(np.nanmin(finite))
    amax = float(np.nanmax(finite))
    span = amax - amin
    return {
        "min_deg": amin,
        "max_deg": amax,
        "span_deg": float(span),
        "mean_deg": float(np.nanmean(finite)),
        "first_deg": float(finite[0]),
        "last_deg": float(finite[-1]),
        "varies": bool(span > 0.1),
    }


def summarize_range_axis(range_m: Sequence[float]) -> Dict[str, Any]:
    arr = np.asarray(range_m, dtype="float64")
    finite = arr[np.isfinite(arr)]
    if not finite.size:
        return {
            "first_gate_m": None,
            "last_gate_m": None,
            "gate_spacing_m_approx": None,
            "gate_count": 0,
            "is_uniform": False,
            "shared_axis": True,
        }
    diffs = np.diff(finite)
    spacing = float(np.nanmedian(diffs)) if diffs.size else None
    uniform = bool(diffs.size == 0 or np.nanmax(np.abs(diffs - np.nanmedian(diffs))) < 0.01)
    return {
        "first_gate_m": float(finite[0]),
        "last_gate_m": float(finite[-1]),
        "gate_spacing_m_approx": spacing,
        "gate_count": int(finite.size),
        "is_uniform": uniform,
        "shared_axis": True,
    }


def classify_sweep_geometry(
    source_sweep_mode: Optional[str],
    azimuth_deg: Sequence[float],
    elevation_deg: Sequence[float],
    top_fixed_angle: Optional[float] = None,
    group_fixed_angle: Optional[float] = None,
) -> Dict[str, Any]:
    source = (source_sweep_mode or "").strip().lower()
    az = summarize_angle(azimuth_deg)
    el = summarize_angle(elevation_deg)
    az_varies = bool(az["varies"])
    el_varies = bool(el["varies"])

    if source == "rhi" or (el_varies and not az_varies):
        scan_type = "RHI"
        fixed_angle_type = "azimuth"
        fixed_angle_deg = az["mean_deg"]
    elif source == "sector" or (az_varies and not el_varies):
        scan_type = "PPI_SECTOR" if source == "sector" else "PPI"
        fixed_angle_type = "elevation"
        fixed_angle_deg = el["mean_deg"]
    else:
        scan_type = "UNKNOWN_OR_COMPLEX"
        fixed_angle_type = "unknown"
        fixed_angle_deg = None

    return {
        "source_sweep_mode": source_sweep_mode,
        "scan_type": scan_type,
        "fixed_angle_type": fixed_angle_type,
        "fixed_angle_deg": fixed_angle_deg,
        "azimuth": az,
        "elevation": el,
        "metadata_fixed_angles": {
            "top_level_sweep_fixed_angle": top_fixed_angle,
            "group_sweep_fixed_angle": group_fixed_angle,
        },
        "geometry_derivation": "coordinate_arrays_primary_metadata_secondary",
    }


def infer_volume_type(scan_types: Sequence[str]) -> str:
    unique = set(scan_types)
    if unique == {"PPI_SECTOR"}:
        return "PPI_SECTOR_VOLUME"
    if unique == {"PPI"}:
        return "PPI_VOLUME"
    if unique == {"RHI"}:
        return "RHI_SET"
    if not unique:
        return "EMPTY"
    if len(unique) > 1:
        return "MIXED_SCAN_SET"
    return next(iter(unique)) + "_SET"


def interp_stops(v: float, stops: Sequence[Tuple[float, Tuple[int, int, int, int]]]) -> Tuple[int, int, int, int]:
    if not math.isfinite(v) or v <= stops[0][0]:
        return stops[0][1]
    for (x0, c0), (x1, c1) in zip(stops[:-1], stops[1:]):
        if v <= x1:
            t = (v - x0) / (x1 - x0) if x1 != x0 else 0.0
            return tuple(int(c0[i] + (c1[i] - c0[i]) * t) for i in range(4))  # type: ignore
    return stops[-1][1]


def color_for(field: str, value: float, vmin: float, vmax: float, nyquist: Optional[float]) -> Tuple[int, int, int, int]:
    f = field.upper()
    if not math.isfinite(value):
        return (0, 0, 0, 0)
    if f == "REF":
        return interp_stops(
            value,
            [
                (-10, (0, 0, 0, 0)),
                (0, (4, 30, 130, 180)),
                (10, (25, 95, 220, 220)),
                (20, (55, 190, 70, 235)),
                (30, (245, 230, 65, 245)),
                (40, (245, 130, 35, 250)),
                (50, (220, 35, 35, 255)),
                (60, (175, 45, 170, 255)),
                (70, (245, 245, 245, 255)),
            ],
        )
    if f == "SW":
        return interp_stops(value, [(0, (8, 8, 20, 80)), (2, (45, 70, 150, 180)), (5, (120, 70, 190, 230)), (10, (230, 110, 220, 250)), (20, (255, 240, 255, 255))])
    if f == "VEL":
        lim = nyquist if nyquist and nyquist > 0 else max(abs(vmin), abs(vmax), 1.0)
        x = max(-1.0, min(1.0, value / lim))
        if x < 0:
            t = abs(x)
            return (int(35 + 20 * (1 - t)), int(70 + 180 * t), int(80 + 50 * t), 245)
        if x > 0:
            t = x
            return (int(80 + 175 * t), int(70 + 50 * (1 - t)), int(40 + 20 * (1 - t)), 245)
        return (25, 25, 25, 100)
    t = 0.5 if vmax <= vmin else max(0.0, min(1.0, (value - vmin) / (vmax - vmin)))
    return (int(30 + 220 * t), int(60 + 100 * (1 - abs(t - 0.5) * 2)), int(220 - 200 * t), 235)


def render_ppi(arr: np.ndarray, azimuth_deg: np.ndarray, range_m: np.ndarray, field: str, out_png: Path, title: str, nyquist: Optional[float], size: int, gate_stride: int, ray_stride: int) -> Dict[str, Any]:
    finite = arr[np.isfinite(arr)]
    vmin = float(np.nanmin(finite)) if finite.size else float("nan")
    vmax = float(np.nanmax(finite)) if finite.size else float("nan")
    max_range_km = max(1.0, float(np.nanmax(range_m)) / 1000.0)
    center = size // 2
    margin = 84
    scale = (size / 2 - margin) / max_range_km
    img = Image.new("RGBA", (size, size), (7, 10, 18, 255))
    draw = ImageDraw.Draw(img, "RGBA")
    drawn = 0
    for ri in range(0, arr.shape[0], max(1, ray_stride)):
        az = math.radians(float(azimuth_deg[ri]))
        sin_az = math.sin(az)
        cos_az = math.cos(az)
        for gi in range(0, arr.shape[1], max(1, gate_stride)):
            val = float(arr[ri, gi])
            color = color_for(field, val, vmin, vmax, nyquist)
            if color[3] == 0:
                continue
            rkm = float(range_m[gi]) / 1000.0
            x = center + rkm * scale * sin_az
            y = center - rkm * scale * cos_az
            draw.point((x, y), fill=color)
            drawn += 1
    draw.rectangle((0, 0, size, 64), fill=(7, 10, 18, 235))
    draw.text((12, 10), title, fill=(235, 240, 250, 255))
    draw.text((12, 34), "Native sector PPI observed gates only; no gridding", fill=(175, 190, 210, 230))
    out_png.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_png)
    return {"png": str(out_png), "render_type": "native_sector_ppi_observed_gates", "drawn_gate_samples": drawn, "image_size_px": [size, size], "gate_stride": gate_stride, "ray_stride": ray_stride}


def render_rhi(arr: np.ndarray, elevation_deg: np.ndarray, range_m: np.ndarray, field: str, out_png: Path, title: str, nyquist: Optional[float], size: int, gate_stride: int, ray_stride: int) -> Dict[str, Any]:
    finite = arr[np.isfinite(arr)]
    vmin = float(np.nanmin(finite)) if finite.size else float("nan")
    vmax = float(np.nanmax(finite)) if finite.size else float("nan")
    width = size
    height = max(420, int(size * 0.55))
    margin_l, margin_r, margin_t, margin_b = 64, 20, 64, 44
    max_range = max(1.0, float(np.nanmax(range_m)))
    min_el = float(np.nanmin(elevation_deg))
    max_el = float(np.nanmax(elevation_deg))
    el_span = max(0.1, max_el - min_el)
    img = Image.new("RGBA", (width, height), (7, 10, 18, 255))
    draw = ImageDraw.Draw(img, "RGBA")
    drawn = 0
    for ri in range(0, arr.shape[0], max(1, ray_stride)):
        el = float(elevation_deg[ri])
        y = height - margin_b - ((el - min_el) / el_span) * (height - margin_t - margin_b)
        for gi in range(0, arr.shape[1], max(1, gate_stride)):
            val = float(arr[ri, gi])
            color = color_for(field, val, vmin, vmax, nyquist)
            if color[3] == 0:
                continue
            x = margin_l + (float(range_m[gi]) / max_range) * (width - margin_l - margin_r)
            draw.point((x, y), fill=color)
            drawn += 1
    draw.rectangle((0, 0, width, 58), fill=(7, 10, 18, 235))
    draw.text((12, 8), title, fill=(235, 240, 250, 255))
    draw.text((12, 31), "Native RHI observed gates only; horizontal axis is range, vertical axis is elevation", fill=(175, 190, 210, 230))
    out_png.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_png)
    return {"png": str(out_png), "render_type": "native_rhi_observed_gates", "drawn_gate_samples": drawn, "image_size_px": [width, height], "gate_stride": gate_stride, "ray_stride": ray_stride}


def top_fixed_angles(ds: Any) -> List[Optional[float]]:
    if "sweep_fixed_angle" not in ds.variables:
        return []
    try:
        return [float(x) for x in np.asarray(ds.variables["sweep_fixed_angle"][:]).ravel()]
    except Exception:
        return []


def group_names(ds: Any) -> List[str]:
    groups = [name for name in ds.groups.keys() if name.startswith("sweep_")]
    return sorted(groups, key=lambda s: int(s.split("_", 1)[1]) if s.split("_", 1)[1].isdigit() else s)


def build_sweep_manifest(ds: Any, gname: str, group: Any, top_fixed: Optional[float], fields: Sequence[str], out_dir: Path, image_size: int, gate_stride: int, ray_stride: int, render: bool) -> Dict[str, Any]:
    _, range_m = read_float_array(group, "range")
    _, azimuth = read_float_array(group, "azimuth")
    _, elevation = read_float_array(group, "elevation")
    time_name, time_values = read_float_array(group, "time") if first_existing_var(group, COORD_ALIASES["time"]) else (None, np.array([]))
    source_mode = scalar_var(group, "sweep_mode")
    group_fixed = scalar_var(group, "sweep_fixed_angle")
    geom = classify_sweep_geometry(source_mode, azimuth, elevation, top_fixed, float(group_fixed) if isinstance(group_fixed, (int, float)) else None)

    nyq_name = first_existing_var(group, COORD_ALIASES["nyquist_velocity"])
    nyquist = None
    nyq_summary = None
    if nyq_name:
        nyq = np.asarray(group.variables[nyq_name][:], dtype="float64")
        finite = nyq[np.isfinite(nyq)]
        if finite.size:
            nyquist = float(np.nanmedian(finite))
            nyq_summary = {"min_mps": float(np.nanmin(finite)), "max_mps": float(np.nanmax(finite)), "median_mps": nyquist}

    sweep: Dict[str, Any] = {
        "sweep_name": gname,
        "sweep_number": scalar_var(group, "sweep_number"),
        "source_sweep_mode": source_mode,
        "scan_type": geom["scan_type"],
        "fixed_angle_type": geom["fixed_angle_type"],
        "fixed_angle_deg": geom["fixed_angle_deg"],
        "dimensions": {name: len(dim) for name, dim in group.dimensions.items()},
        "ray_count": int(len(time_values)) if time_values.size else int(len(azimuth)),
        "gate_count": int(len(range_m)),
        "geometry": geom,
        "range": summarize_range_axis(range_m),
        "time": summarize_time_axis(time_values),
        "nyquist_velocity": nyq_summary,
        "adaptive_scan": {"adt_detected": False, "per_ray_prt": False, "per_ray_gate_count": False, "per_ray_range_axis": False, "geometry_model": "regular_sweep"},
        "available_variables": list(group.variables.keys()),
        "fields": {},
        "renders": [],
    }

    for requested in fields:
        var_name = canonical_field(group, requested)
        if not var_name:
            sweep["fields"][requested] = {"present": False}
            continue
        var = group.variables[var_name]
        arr = read_masked_field(var)
        stats = finite_stats(arr)
        stats.update({"present": True, "source_variable": var_name, "dtype": str(var.dtype), "units": json_safe(getattr(var, "units", None)), "long_name": json_safe(getattr(var, "long_name", None))})
        sweep["fields"][requested] = stats
        if render:
            require_image_deps()
            png = out_dir / "quicklooks" / f"{gname}_{requested}.png"
            title = f"StormDeck {requested} | {getattr(ds, 'site_name', '')} | {getattr(ds, 'scan_name', '')} | {gname} | {geom['scan_type']}"
            if geom["scan_type"] == "RHI":
                info = render_rhi(arr, elevation, range_m, requested, png, title, nyquist, image_size, gate_stride, ray_stride)
            else:
                info = render_ppi(arr, azimuth, range_m, requested, png, title, nyquist, image_size, gate_stride, ray_stride)
            sweep["renders"].append(info)
    return sweep


def summarize_time_axis(time_s: Sequence[float]) -> Dict[str, Any]:
    arr = np.asarray(time_s, dtype="float64")
    finite = arr[np.isfinite(arr)]
    if not finite.size:
        return {"start_offset_s": None, "end_offset_s": None, "duration_s": None}
    start = float(finite[0])
    end = float(finite[-1])
    return {"start_offset_s": start, "end_offset_s": end, "duration_s": float(end - start), "first_s": start, "last_s": end}


def build_case_manifest(nc_path: Path, out_dir: Path, fields: Sequence[str], image_size: int, gate_stride: int, ray_stride: int, render: bool) -> Dict[str, Any]:
    Dataset_cls = require_dataset_dep()
    ds = Dataset_cls(str(nc_path), "r")
    try:
        names = group_names(ds)
        fixed = top_fixed_angles(ds)
        sweeps = []
        for idx, gname in enumerate(names):
            top_fixed = fixed[idx] if idx < len(fixed) else None
            sweeps.append(build_sweep_manifest(ds, gname, ds.groups[gname], top_fixed, fields, out_dir, image_size, gate_stride, ray_stride, render))
        scan_types = [s["scan_type"] for s in sweeps]
        time_offsets = [s["time"]["end_offset_s"] for s in sweeps if s["time"].get("end_offset_s") is not None]
        manifest = {
            "stormdeck_schema": "stormdeck.case_probe.v0",
            "source_nc": str(nc_path),
            "source_format": "CfRadial2 NetCDF4 grouped sweep_*",
            "netcdf_data_model": json_safe(getattr(ds, "data_model", None)),
            "radar_id": json_safe(getattr(ds, "instrument_name", getattr(ds, "site_name", None))),
            "site_name": json_safe(getattr(ds, "site_name", None)),
            "scan_name": json_safe(getattr(ds, "scan_name", None)),
            "start_time": json_safe(getattr(ds, "start_time", None)),
            "end_time": json_safe(getattr(ds, "end_time", None)),
            "time_coverage_start": json_safe(getattr(ds, "time_coverage_start", None)),
            "time_coverage_end": json_safe(getattr(ds, "time_coverage_end", None)),
            "duration_s_from_offsets": float(max(time_offsets)) if time_offsets else None,
            "sweep_count": len(sweeps),
            "volume_type": infer_volume_type(scan_types),
            "adaptive_scan": {"adt_detected": False, "per_ray_prt": False, "per_ray_gate_count": False, "per_ray_range_axis": False, "geometry_model": "regular_sweep", "future_note": "ADT can vary gate count and PRT per radial; current sample uses shared range axis per sweep."},
            "scientific_status": "observed_native_radar_data_quicklook_not_gridded_not_interpolated",
            "sweeps": sweeps,
        }
        return manifest
    finally:
        ds.close()


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Probe ATD/KATD CfRadial grouped sweep files and export StormDeck manifest plus quicklooks.")
    parser.add_argument("inputs", nargs="+", help="Input CfRadial NetCDF file or files")
    parser.add_argument("--out", default="stormdeck_case_probe_export", help="Output directory")
    parser.add_argument("--fields", default="REF,VEL,SW", help="Comma-separated fields to inspect and render")
    parser.add_argument("--image-size", type=int, default=1400, help="Quicklook image size in pixels")
    parser.add_argument("--gate-stride", type=int, default=2, help="Draw every Nth gate")
    parser.add_argument("--ray-stride", type=int, default=1, help="Draw every Nth ray")
    parser.add_argument("--no-render", action="store_true", help="Write manifests only")
    args = parser.parse_args(argv)

    root = Path(args.out).expanduser().resolve()
    fields = [f.strip() for f in args.fields.split(",") if f.strip()]
    root.mkdir(parents=True, exist_ok=True)
    written = []
    for input_name in args.inputs:
        nc_path = Path(input_name).expanduser().resolve()
        case_out = root / nc_path.stem
        case_out.mkdir(parents=True, exist_ok=True)
        manifest = build_case_manifest(nc_path, case_out, fields, args.image_size, max(1, args.gate_stride), max(1, args.ray_stride), not args.no_render)
        manifest_path = case_out / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
        written.append(manifest_path)
        print(f"Wrote manifest: {manifest_path}")
        print(f"Volume type: {manifest['volume_type']} | sweeps={manifest['sweep_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
