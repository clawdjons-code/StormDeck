#!/usr/bin/env python3
"""Export a StormDeck KATD replay artifact from Cf/Radial NetCDF.

This is the source-faithful bridge between internal KATD Level 2 CFILE data
(converted with cfile_to_cfradial) and the later StormDeck cockpit. It writes
versioned JSON sidecars and native observed-gate previews. It does not grid,
interpolate, infer 360-degree coverage, or require GPU acceleration.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from stormdeck_radar_arrays import masked_numeric_array

FIELD_ALIASES: Dict[str, List[str]] = {
    "REF": ["REF", "DBZ", "DZ", "ZH", "Z", "reflectivity", "corrected_reflectivity"],
    "VEL": ["VEL", "VR", "V", "velocity", "radial_velocity"],
    "V1D": ["V1D"],
    "SW": ["SW", "WIDTH", "W", "spectrum_width", "spectrum_width_h"],
    "ZDR": ["ZDR", "differential_reflectivity"],
    "LDR": ["LDR"],
    "DR": ["DR"],
    "PHI": ["PHI", "PHIDP", "PhiDP", "differential_phase"],
    "RHO": ["RHO", "RHOHV", "rhoHV", "cross_correlation_ratio"],
    "RHX": ["RHX"],
    "NYQ": ["NYQ", "nyquist_velocity", "nyquist"],
}

COORD_ALIASES: Dict[str, List[str]] = {
    "range": ["range", "gate_range"],
    "azimuth": ["azimuth", "az", "ray_azimuth"],
    "elevation": ["elevation", "el", "ray_elevation"],
    "time": ["time"],
}

QC_FLAG_NAMES = ["THR", "THV", "THW", "THA", "OVV", "OVW", "CLTR", "CLTV", "CLTW"]
DEFAULT_FIELDS = ["REF", "VEL", "SW"]
ALL_SUMMARY_FIELDS = ["REF", "VEL", "V1D", "SW", "ZDR", "LDR", "DR", "PHI", "RHO", "RHX", "NYQ"]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def json_safe(value: Any) -> Any:
    try:
        import numpy as np  # type: ignore

        if isinstance(value, np.generic):
            return value.item()
        if isinstance(value, np.ndarray):
            return value.tolist()
    except Exception:
        pass
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    return str(value)


def case_id_from_path(path: Path) -> str:
    """Return a stable case ID from common KATD base-data names."""
    stem = path.stem
    match = re.search(r"KATD_Base_Data_(\d{8})_(\d{6})_", stem)
    if match:
        return f"KATD_{match.group(1)}_{match.group(2)}"
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", stem).strip("_")
    return safe or "katd_replay_case"


def artifact_layout(case_dir: Path, case_id: str, frame_id: str) -> Dict[str, Path]:
    frame_dir = case_dir / "frames" / frame_id
    return {
        "case_dir": case_dir,
        "case_manifest": case_dir / "case_manifest.json",
        "case_provenance": case_dir / "provenance.json",
        "frame_dir": frame_dir,
        "frame_manifest": frame_dir / "frame_manifest.json",
        "geometry_summary": frame_dir / "geometry_summary.json",
        "field_stats": frame_dir / "field_stats.json",
        "qc_flags_summary": frame_dir / "qc_flags_summary.json",
        "preview_dir": frame_dir / "previews",
        "data_dir": frame_dir / "data",
    }


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
    aliases = FIELD_ALIASES.get(requested.upper(), [requested])
    found = first_existing_var(group, aliases)
    if found:
        return found
    lower = {name.lower(): name for name in group.variables.keys()}
    return lower.get(requested.lower())


def read_coord(group: Any, logical_name: str):
    import numpy as np  # type: ignore

    name = first_existing_var(group, COORD_ALIASES[logical_name])
    if not name:
        raise ValueError(f"Required coordinate missing: {logical_name}; variables={list(group.variables.keys())}")
    return name, np.asarray(group.variables[name][:], dtype="float64")


def finite_percentiles(arr: Any) -> Dict[str, Any]:
    import numpy as np  # type: ignore

    finite = arr[np.isfinite(arr)]
    stats: Dict[str, Any] = {
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
                "p05": float(np.nanpercentile(finite, 5)),
                "p50": float(np.nanpercentile(finite, 50)),
                "p95": float(np.nanpercentile(finite, 95)),
                "p99": float(np.nanpercentile(finite, 99)),
            }
        )
    else:
        stats.update({"min": None, "max": None, "mean": None, "p01": None, "p05": None, "p50": None, "p95": None, "p99": None})
    return stats


def summarize_field_var(canonical_name: str, var: Any) -> Dict[str, Any]:
    arr = masked_numeric_array(var)
    summary = {
        "present": True,
        "source_variable": getattr(var, "name", canonical_name),
        "units": json_safe(getattr(var, "units", None)),
        "long_name": json_safe(getattr(var, "long_name", None)),
        "standard_name": json_safe(getattr(var, "standard_name", None)),
        "dtype": str(getattr(var, "dtype", "unknown")),
        "shape": list(getattr(var, "shape", arr.shape)),
        "fill_value": json_safe(getattr(var, "_FillValue", None)),
    }
    summary.update(finite_percentiles(arr))
    if canonical_name.upper() in {"VEL", "V1D"}:
        summary["nyquist_source"] = "nyquist_velocity and/or NYQ"
    return summary


def summarize_qc_flag_var(name: str, var: Any) -> Dict[str, Any]:
    import numpy as np  # type: ignore

    arr = var[:]
    raw = np.asarray(arr)
    fill = getattr(var, "_FillValue", None)
    valid = np.ones(raw.shape, dtype=bool)
    if fill is not None:
        valid &= raw != fill
    valid_values = raw[valid]
    nonzero = int(np.count_nonzero(valid_values)) if valid_values.size else 0
    valid_count = int(valid_values.size)
    return {
        "present": True,
        "source_variable": name,
        "dtype": str(getattr(var, "dtype", raw.dtype)),
        "shape": list(getattr(var, "shape", raw.shape)),
        "fill_value": json_safe(fill),
        "valid_gate_count": valid_count,
        "missing_gate_count": int(raw.size - valid_count),
        "nonzero_count": nonzero,
        "nonzero_fraction": (nonzero / valid_count) if valid_count else None,
        "flag_values": json_safe(getattr(var, "flag_values", None)),
        "flag_meanings": json_safe(getattr(var, "flag_meanings", None)),
        "units": json_safe(getattr(var, "units", None)),
        "long_name": json_safe(getattr(var, "long_name", None)),
        "standard_name": json_safe(getattr(var, "standard_name", None)),
    }


def summarize_range(range_m: Any) -> Dict[str, Any]:
    import numpy as np  # type: ignore

    finite = range_m[np.isfinite(range_m)]
    if finite.size == 0:
        return {"units": "meters", "gate_count": 0, "min_m": None, "max_m": None, "spacing_median_m": None, "is_uniform": False}
    diffs = np.diff(finite)
    spacing = float(np.nanmedian(diffs)) if diffs.size else None
    is_uniform = bool(diffs.size == 0 or np.nanmax(np.abs(diffs - np.nanmedian(diffs))) < 0.01)
    return {
        "units": "meters",
        "gate_count": int(finite.size),
        "min_m": float(np.nanmin(finite)),
        "max_m": float(np.nanmax(finite)),
        "spacing_median_m": spacing,
        "first_gate_m": float(finite[0]),
        "last_gate_m": float(finite[-1]),
        "is_uniform": is_uniform,
    }


def summarize_angle(values: Any) -> Dict[str, Any]:
    import numpy as np  # type: ignore

    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return {"units": "degrees", "ray_count": 0, "min_deg": None, "max_deg": None, "span_deg": None, "mean_deg": None, "varies": False}
    amin = float(np.nanmin(finite))
    amax = float(np.nanmax(finite))
    span = amax - amin
    return {
        "units": "degrees",
        "ray_count": int(finite.size),
        "min_deg": amin,
        "max_deg": amax,
        "span_deg": float(span),
        "mean_deg": float(np.nanmean(finite)),
        "first_deg": float(finite[0]),
        "last_deg": float(finite[-1]),
        "varies": bool(span > 0.1),
    }


def summarize_time(time_s: Any) -> Dict[str, Any]:
    import numpy as np  # type: ignore

    finite = time_s[np.isfinite(time_s)]
    if finite.size == 0:
        return {"start_offset_s": None, "end_offset_s": None, "duration_seconds": None}
    start = float(finite[0])
    end = float(finite[-1])
    return {"start_offset_s": start, "end_offset_s": end, "duration_seconds": float(end - start), "ray_count": int(finite.size)}


def is_rhi_like(azimuth: Any, elevation: Any, sweep_mode: Optional[str]) -> bool:
    if (sweep_mode or "").strip().lower() == "rhi":
        return True
    az = summarize_angle(azimuth)
    el = summarize_angle(elevation)
    return bool(el.get("varies") and not az.get("varies"))


def interp_color(v: float, stops: Sequence[Tuple[float, Tuple[int, int, int, int]]]) -> Tuple[int, int, int, int]:
    if not math.isfinite(v) or v <= stops[0][0]:
        return stops[0][1]
    for (x0, c0), (x1, c1) in zip(stops[:-1], stops[1:]):
        if v <= x1:
            t = 0.0 if x1 == x0 else (v - x0) / (x1 - x0)
            return tuple(int(c0[i] + (c1[i] - c0[i]) * t) for i in range(4))  # type: ignore[return-value]
    return stops[-1][1]


def color_for(field: str, value: float, vmin: float, vmax: float, nyquist: Optional[float]) -> Tuple[int, int, int, int]:
    if not math.isfinite(value):
        return (0, 0, 0, 0)
    f = field.upper()
    if f == "REF":
        return interp_color(value, [(-10, (0, 0, 0, 0)), (0, (4, 30, 130, 180)), (10, (25, 95, 220, 220)), (20, (55, 190, 70, 235)), (30, (245, 230, 65, 245)), (40, (245, 130, 35, 250)), (50, (220, 35, 35, 255)), (60, (175, 45, 170, 255)), (70, (245, 245, 245, 255))])
    if f in {"VEL", "V1D"}:
        lim = nyquist if nyquist and nyquist > 0 else max(abs(vmin), abs(vmax), 1.0)
        x = max(-1.0, min(1.0, value / lim))
        if x < 0:
            t = abs(x)
            return (int(35 + 20 * (1 - t)), int(70 + 180 * t), int(80 + 50 * t), 245)
        if x > 0:
            t = x
            return (int(80 + 175 * t), int(70 + 50 * (1 - t)), int(40 + 20 * (1 - t)), 245)
        return (25, 25, 25, 100)
    if f == "SW":
        return interp_color(value, [(0, (8, 8, 20, 80)), (2, (45, 70, 150, 180)), (5, (120, 70, 190, 230)), (10, (230, 110, 220, 250)), (20, (255, 240, 255, 255))])
    t = 0.5 if vmax <= vmin else max(0.0, min(1.0, (value - vmin) / (vmax - vmin)))
    return (int(30 + 220 * t), int(60 + 100 * (1 - abs(t - 0.5) * 2)), int(220 - 200 * t), 235)


def render_native_preview(
    arr: Any,
    range_m: Any,
    azimuth: Any,
    elevation: Any,
    field: str,
    out_png: Path,
    title: str,
    nyquist: Optional[float],
    image_size: int,
    gate_stride: int,
    ray_stride: int,
    rhi: bool,
) -> Dict[str, Any]:
    import numpy as np  # type: ignore
    from PIL import Image, ImageDraw  # type: ignore

    finite = arr[np.isfinite(arr)]
    vmin = float(np.nanmin(finite)) if finite.size else float("nan")
    vmax = float(np.nanmax(finite)) if finite.size else float("nan")
    out_png.parent.mkdir(parents=True, exist_ok=True)

    if rhi:
        width = image_size
        height = max(420, int(image_size * 0.55))
        margin_l, margin_r, margin_t, margin_b = 64, 24, 64, 46
        max_range = max(1.0, float(np.nanmax(range_m)))
        min_el = float(np.nanmin(elevation))
        max_el = float(np.nanmax(elevation))
        el_span = max(0.1, max_el - min_el)
        img = Image.new("RGBA", (width, height), (7, 10, 18, 255))
        draw = ImageDraw.Draw(img, "RGBA")
        drawn = 0
        for ri in range(0, arr.shape[0], max(1, ray_stride)):
            y = height - margin_b - ((float(elevation[ri]) - min_el) / el_span) * (height - margin_t - margin_b)
            for gi in range(0, arr.shape[1], max(1, gate_stride)):
                color = color_for(field, float(arr[ri, gi]), vmin, vmax, nyquist)
                if color[3] == 0:
                    continue
                x = margin_l + (float(range_m[gi]) / max_range) * (width - margin_l - margin_r)
                draw.point((x, y), fill=color)
                drawn += 1
        draw.rectangle((0, 0, width, 60), fill=(7, 10, 18, 235))
        draw.text((12, 8), title, fill=(235, 240, 250, 255))
        draw.text((12, 32), "Native RHI observed gates only; not gridded/interpolated", fill=(175, 190, 210, 230))
        img.save(out_png)
        return {"schema": "stormdeck.native_ppi_preview.v0", "path": str(out_png), "render_type": "native_rhi_observed_gates", "drawn_gate_samples": drawn, "image_size_px": [width, height], "gate_stride": gate_stride, "ray_stride": ray_stride}

    size = image_size
    center = size // 2
    margin = 84
    max_range_km = max(1.0, float(np.nanmax(range_m)) / 1000.0)
    scale = (size / 2 - margin) / max_range_km
    img = Image.new("RGBA", (size, size), (7, 10, 18, 255))
    draw = ImageDraw.Draw(img, "RGBA")
    drawn = 0
    for ri in range(0, arr.shape[0], max(1, ray_stride)):
        az = math.radians(float(azimuth[ri]))
        sin_az = math.sin(az)
        cos_az = math.cos(az)
        for gi in range(0, arr.shape[1], max(1, gate_stride)):
            color = color_for(field, float(arr[ri, gi]), vmin, vmax, nyquist)
            if color[3] == 0:
                continue
            rkm = float(range_m[gi]) / 1000.0
            x = center + rkm * scale * sin_az
            y = center - rkm * scale * cos_az
            draw.point((x, y), fill=color)
            drawn += 1
    draw.rectangle((0, 0, size, 66), fill=(7, 10, 18, 235))
    draw.text((12, 10), title, fill=(235, 240, 250, 255))
    draw.text((12, 36), "Native observed gates only; not gridded/interpolated; no synthetic 360° fill", fill=(175, 190, 210, 230))
    img.save(out_png)
    return {"schema": "stormdeck.native_ppi_preview.v0", "path": str(out_png), "render_type": "native_sector_ppi_observed_gates", "drawn_gate_samples": drawn, "image_size_px": [size, size], "gate_stride": gate_stride, "ray_stride": ray_stride}


def group_names(ds: Any) -> List[str]:
    names = [name for name in ds.groups.keys() if name.startswith("sweep_")]
    if names:
        return sorted(names, key=lambda s: int(s.split("_", 1)[1]) if s.split("_", 1)[1].isdigit() else s)
    return ["root"]


def get_group(ds: Any, name: str) -> Any:
    return ds if name == "root" else ds.groups[name]


def dimensions_dict(group: Any) -> Dict[str, int]:
    return {name: int(len(dim)) for name, dim in group.dimensions.items()}


def scalar_var(group: Any, name: str) -> Optional[Any]:
    if name not in group.variables:
        return None
    try:
        return json_safe(group.variables[name][()])
    except Exception:
        return None


def global_attrs(ds: Any) -> Dict[str, Any]:
    return {name: json_safe(getattr(ds, name)) for name in ds.ncattrs()}


def file_sha256(path: Path, enabled: bool) -> Optional[str]:
    if not enabled or not path.exists() or not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def find_source_cfile(nc_path: Path, explicit: Optional[Path]) -> Optional[Path]:
    if explicit:
        return explicit
    candidates = [nc_path.with_suffix(".cfl"), nc_path.with_suffix(".CFILE")]
    for p in candidates:
        if p.exists():
            return p
    return None


def build_frame_artifacts(
    ds: Any,
    nc_path: Path,
    source_cfile: Optional[Path],
    case_id: str,
    frame_id: str,
    sweep_name: str,
    frame_index: int,
    layout: Dict[str, Path],
    requested_previews: Sequence[str],
    image_size: int,
    gate_stride: int,
    ray_stride: int,
    render: bool,
    created_utc: str,
) -> Dict[str, Any]:
    import numpy as np  # type: ignore

    group = get_group(ds, sweep_name)
    _, range_m = read_coord(group, "range")
    _, azimuth = read_coord(group, "azimuth")
    _, elevation = read_coord(group, "elevation")
    time_name = first_existing_var(group, COORD_ALIASES["time"])
    time_values = np.asarray(group.variables[time_name][:], dtype="float64") if time_name else np.array([])
    sweep_mode = scalar_var(group, "sweep_mode")
    rhi = is_rhi_like(azimuth, elevation, sweep_mode if isinstance(sweep_mode, str) else None)
    scan_type = "RHI" if rhi else "PPI_SECTOR_OR_PPI"

    nyq_summary = None
    nyquist_for_render = None
    nyq_name = first_existing_var(group, ["nyquist_velocity", "NYQ", "nyquist"])
    if nyq_name:
        nyq = np.asarray(group.variables[nyq_name][:], dtype="float64")
        finite = nyq[np.isfinite(nyq)]
        if finite.size:
            nyq_summary = {"source_variable": nyq_name, "min_mps": float(np.nanmin(finite)), "max_mps": float(np.nanmax(finite)), "median_mps": float(np.nanmedian(finite))}
            nyquist_for_render = float(np.nanmedian(finite))

    geometry_summary = {
        "schema": "stormdeck.katd_geometry_summary.v0",
        "schema_version": 0,
        "created_utc": created_utc,
        "case_id": case_id,
        "frame_id": frame_id,
        "source_cfradial": str(nc_path),
        "sweep_group": sweep_name,
        "scan_type": scan_type,
        "dimensions": dimensions_dict(group),
        "coordinates": {
            "range": summarize_range(range_m),
            "azimuth": summarize_angle(azimuth),
            "elevation": summarize_angle(elevation),
            "time": summarize_time(time_values),
        },
        "site": {
            "latitude_deg": json_safe(getattr(ds, "latitude", None)) or scalar_var(ds, "latitude"),
            "longitude_deg": json_safe(getattr(ds, "longitude", None)) or scalar_var(ds, "longitude"),
            "altitude_m": json_safe(getattr(ds, "altitude", None)) or scalar_var(ds, "altitude"),
        },
        "sweep": {
            "sweep_mode": sweep_mode,
            "sweep_number": scalar_var(group, "sweep_number"),
            "sweep_fixed_angle": scalar_var(group, "sweep_fixed_angle"),
            "nyquist_velocity": nyq_summary,
        },
        "coverage": {
            "sector_like": bool(summarize_angle(azimuth).get("span_deg") is not None and (summarize_angle(azimuth).get("span_deg") or 0) < 359.0),
            "full_360_observed": bool((summarize_angle(azimuth).get("span_deg") or 0) >= 359.0),
            "notes": ["Coverage inferred from source coordinates, not assumed."],
        },
    }

    field_stats: Dict[str, Any] = {"schema": "stormdeck.katd_field_stats.v0", "schema_version": 0, "created_utc": created_utc, "case_id": case_id, "frame_id": frame_id, "sweep_group": sweep_name, "fields": {}, "missing_requested_fields": []}
    for canonical in ALL_SUMMARY_FIELDS:
        var_name = canonical_field(group, canonical)
        if not var_name:
            field_stats["fields"][canonical] = {"present": False}
            field_stats["missing_requested_fields"].append(canonical)
            continue
        field_stats["fields"][canonical] = summarize_field_var(canonical, group.variables[var_name])

    qc_summary: Dict[str, Any] = {"schema": "stormdeck.katd_qc_flags_summary.v0", "schema_version": 0, "created_utc": created_utc, "case_id": case_id, "frame_id": frame_id, "sweep_group": sweep_name, "flags": {}, "missing_flags": [], "warnings": ["Flag names are preserved from source. Avoid strong semantic claims until definitions are confirmed against source documentation."]}
    for flag in QC_FLAG_NAMES:
        var_name = first_existing_var(group, [flag])
        if not var_name:
            qc_summary["flags"][flag] = {"present": False}
            qc_summary["missing_flags"].append(flag)
            continue
        qc_summary["flags"][flag] = summarize_qc_flag_var(var_name, group.variables[var_name])

    previews = []
    if render:
        for field in requested_previews:
            var_name = canonical_field(group, field)
            if not var_name:
                continue
            arr = masked_numeric_array(group.variables[var_name])
            safe_sweep = re.sub(r"[^A-Za-z0-9_.-]+", "_", sweep_name)
            png = layout["preview_dir"] / f"ppi_{field}_{safe_sweep}.png"
            radar = json_safe(getattr(ds, "instrument_name", getattr(ds, "site_name", "KATD")))
            title = f"StormDeck {field} | {radar} | {sweep_name} | {scan_type}"
            previews.append(render_native_preview(arr, range_m, azimuth, elevation, field, png, title, nyquist_for_render, image_size, gate_stride, ray_stride, rhi))

    frame_manifest = {
        "schema": "stormdeck.katd_frame_manifest.v0",
        "schema_version": 0,
        "created_utc": created_utc,
        "case_id": case_id,
        "frame_id": frame_id,
        "frame_index": frame_index,
        "source": {
            "source_cfile": str(source_cfile) if source_cfile else None,
            "source_cfradial": str(nc_path),
            "cfradial_convention": json_safe(getattr(ds, "Conventions", None)),
            "cfradial_version": json_safe(getattr(ds, "version", None)),
            "group": sweep_name,
        },
        "time": {
            "coverage_start": json_safe(getattr(ds, "time_coverage_start", None)),
            "coverage_end": json_safe(getattr(ds, "time_coverage_end", None)),
            "start_time": json_safe(getattr(ds, "start_time", None)),
            "end_time": json_safe(getattr(ds, "end_time", None)),
            "duration_seconds": geometry_summary["coordinates"]["time"].get("duration_seconds"),
            "replay_time_utc": json_safe(getattr(ds, "time_coverage_start", None)),
        },
        "sweep": {
            "group": sweep_name,
            "sweep_index": frame_index,
            "sweep_mode": sweep_mode,
            "scan_type": scan_type,
            "fixed_angle_deg": geometry_summary["coordinates"]["elevation"].get("mean_deg") if not rhi else geometry_summary["coordinates"]["azimuth"].get("mean_deg"),
            "ray_count": int(len(azimuth)),
            "gate_count": int(len(range_m)),
            "prt_count": int(len(group.dimensions["prt"])) if "prt" in group.dimensions else None,
        },
        "available_fields": [name for name, info in field_stats["fields"].items() if info.get("present")],
        "available_qc_flags": [name for name, info in qc_summary["flags"].items() if info.get("present")],
        "artifacts": {
            "geometry_summary": "geometry_summary.json",
            "field_stats": "field_stats.json",
            "qc_flags_summary": "qc_flags_summary.json",
            "previews": [str(Path(p["path"]).relative_to(layout["frame_dir"])) for p in previews],
        },
        "render_policy": {"native_observed_gates_only": True, "gridded": False, "interpolated": False, "synthetic_fill": False},
        "warnings": ["Research radar data; use with provenance/QC context.", "Observed-gate native preview only; not gridded or interpolated."],
    }

    for key, data in [("geometry_summary", geometry_summary), ("field_stats", field_stats), ("qc_flags_summary", qc_summary), ("frame_manifest", frame_manifest)]:
        path = layout[key]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")

    return frame_manifest


def export_replay_artifact(
    nc_paths: Sequence[Path],
    out_dir: Path,
    case_id: Optional[str],
    fields: Sequence[str],
    source_cfile: Optional[Path],
    image_size: int,
    gate_stride: int,
    ray_stride: int,
    render: bool,
    checksums: bool,
) -> Dict[str, Any]:
    from netCDF4 import Dataset  # type: ignore

    created_utc = utc_now_iso()
    if not nc_paths:
        raise ValueError("No input NetCDF files provided")
    resolved_case_id = case_id or case_id_from_path(nc_paths[0])
    case_dir = out_dir.expanduser().resolve()
    case_dir.mkdir(parents=True, exist_ok=True)

    frames = []
    source_inputs = []
    frame_index = 0
    radar_meta: Dict[str, Any] = {}
    for nc_path in nc_paths:
        nc_path = nc_path.expanduser().resolve()
        cfile = find_source_cfile(nc_path, source_cfile)
        source_inputs.append({"source_type": "katd_level2_cfile" if cfile else "cfradial_netcdf", "path": str(cfile) if cfile else None, "converted_cfradial_path": str(nc_path), "cfile_sha256": file_sha256(cfile, checksums) if cfile else None, "cfradial_sha256": file_sha256(nc_path, checksums)})
        ds = Dataset(str(nc_path), "r")
        try:
            if not radar_meta:
                radar_meta = {"id": json_safe(getattr(ds, "instrument_name", getattr(ds, "site_name", "KATD"))), "name": json_safe(getattr(ds, "site_name", "NSSL Advanced Technology Demonstrator")), "scan_name": json_safe(getattr(ds, "scan_name", None)), "global_attrs": global_attrs(ds)}
            for sweep_name in group_names(ds):
                frame_id = f"frame_{frame_index:06d}"
                layout = artifact_layout(case_dir, resolved_case_id, frame_id)
                frame_manifest = build_frame_artifacts(ds, nc_path, cfile, resolved_case_id, frame_id, sweep_name, frame_index, layout, fields, image_size, gate_stride, ray_stride, render, created_utc)
                frames.append({"frame_id": frame_id, "manifest_path": str(Path("frames") / frame_id / "frame_manifest.json"), "source_cfradial": str(nc_path), "sweep_group": sweep_name, "time": frame_manifest["time"], "sweep": frame_manifest["sweep"]})
                frame_index += 1
        finally:
            ds.close()

    time_starts = [f["time"].get("coverage_start") for f in frames if f["time"].get("coverage_start")]
    time_ends = [f["time"].get("coverage_end") for f in frames if f["time"].get("coverage_end")]
    case_manifest = {
        "schema": "stormdeck.katd_case_manifest.v0",
        "schema_version": 0,
        "created_utc": created_utc,
        "case_id": resolved_case_id,
        "title": f"KATD replay case {resolved_case_id}",
        "radar": {"id": radar_meta.get("id", "KATD"), "name": radar_meta.get("name", "NSSL Advanced Technology Demonstrator"), "class": "research_dual_pol_s_band_phased_array", "coverage_note": "Sector PAR coverage; do not imply full 360-degree coverage unless source geometry proves it."},
        "replay": {"mode": "archived_case_replay", "frame_count": len(frames), "time_coverage_start": min(time_starts) if time_starts else None, "time_coverage_end": max(time_ends) if time_ends else None, "native_frame_cadence_seconds": None, "field_value_deltas_included": False},
        "source_inputs": source_inputs,
        "frames": frames,
        "warnings": ["Research radar data; minimally quality controlled.", "Observed-gate native preview only; not gridded or interpolated.", "Metadata-safe replay artifact; no field-value delta claims."],
    }
    provenance = {
        "schema": "stormdeck.katd_provenance.v0",
        "schema_version": 0,
        "created_utc": created_utc,
        "created_by": "scripts/stormdeck_katd_replay_export.py",
        "source_chain": source_inputs,
        "environment": {"host_role": "backend_data_cache", "gpu_required": False, "python_version": sys.version.split()[0], "platform": sys.platform},
        "trust_labels": {"research_radar": True, "observed_gates_only": True, "gridded": False, "interpolated": False, "operational_warning_product": False},
    }
    (case_dir / "case_manifest.json").write_text(json.dumps(case_manifest, indent=2, sort_keys=True), encoding="utf-8")
    (case_dir / "provenance.json").write_text(json.dumps(provenance, indent=2, sort_keys=True), encoding="utf-8")
    return case_manifest


def expand_inputs(patterns: Sequence[str]) -> List[Path]:
    import glob

    paths: List[Path] = []
    for item in patterns:
        matches = sorted(glob.glob(item))
        if matches:
            paths.extend(Path(m) for m in matches)
        else:
            paths.append(Path(item))
    return paths


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Export a source-faithful StormDeck KATD replay artifact from Cf/Radial NetCDF.")
    parser.add_argument("inputs", nargs="+", help="Input Cf/Radial NetCDF file(s); shell globs are accepted when quoted")
    parser.add_argument("--out", required=True, help="Output case artifact directory")
    parser.add_argument("--case-id", default=None, help="Case ID; defaults from first KATD filename")
    parser.add_argument("--source-cfile", default=None, help="Optional source CFILE path for provenance when processing one converted .nc")
    parser.add_argument("--fields", default=",".join(DEFAULT_FIELDS), help="Comma-separated fields to render as previews")
    parser.add_argument("--image-size", type=int, default=1400, help="Preview image size in pixels")
    parser.add_argument("--gate-stride", type=int, default=2, help="Draw every Nth gate in previews")
    parser.add_argument("--ray-stride", type=int, default=1, help="Draw every Nth ray in previews")
    parser.add_argument("--no-render", action="store_true", help="Write JSON artifacts only")
    parser.add_argument("--checksums", action="store_true", help="Compute SHA-256 checksums for source files")
    args = parser.parse_args(argv)

    fields = [f.strip() for f in args.fields.split(",") if f.strip()]
    paths = expand_inputs(args.inputs)
    source_cfile = Path(args.source_cfile).expanduser().resolve() if args.source_cfile else None
    manifest = export_replay_artifact(paths, Path(args.out), args.case_id, fields, source_cfile, max(480, args.image_size), max(1, args.gate_stride), max(1, args.ray_stride), not args.no_render, args.checksums)
    print(f"Wrote StormDeck KATD replay artifact: {Path(args.out).expanduser().resolve()}")
    print(f"Case ID: {manifest['case_id']} | frames={manifest['replay']['frame_count']}")
    print("Primary manifest: case_manifest.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
