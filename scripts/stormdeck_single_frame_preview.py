#!/usr/bin/env python3
"""
StormDeck single-frame CfRadial preview renderer.

Purpose
-------
Create a scientifically honest first preview artifact from one KATD/ATD CfRadial
volume frame before building the full interactive renderer.

Inputs
------
- A converted CfRadial NetCDF file (.nc), or
- A Level-2 CFILE (.cfl/.CFILE) if `cfile_to_cfradial` is available.

Outputs
-------
- quicklook_<FIELD>_<SWEEP>.png: native polar/radial plan-view preview
- frame_manifest.json: dimensions, field stats, source/provenance

Dependencies on wea-fs
----------------------
DNF packages already validated in the group transcript:
- python3-numpy
- python3-netcdf4
- python3-pillow

This intentionally avoids matplotlib, pyart, cartopy, geopandas, and online maps.
It renders observed radar gates only; it does not grid or interpolate.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from stormdeck_radar_arrays import masked_numeric_array


def _require_runtime_deps() -> Tuple[Any, Any, Any, Any]:
    """Import heavy deps lazily so --help works on systems without them."""
    try:
        import numpy as np  # type: ignore
        from netCDF4 import Dataset  # type: ignore
        from PIL import Image, ImageDraw  # type: ignore
    except Exception:  # pragma: no cover - depends on target host
        print(
            "Missing runtime dependency. On wea-fs install/verify: "
            "sudo dnf install python3-numpy python3-netcdf4 python3-pillow",
            file=sys.stderr,
        )
        raise
    return np, Dataset, Image, ImageDraw


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
    "nyquist_velocity": ["nyquist_velocity", "nyquist", "NYQ"],
}


def json_safe(value: Any) -> Any:
    """Convert netCDF/numpy values into JSON-safe scalars/lists."""
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
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    return str(value)


def first_existing_var(group: Any, names: Iterable[str]) -> Optional[str]:
    vars_lower = {name.lower(): name for name in group.variables.keys()}
    for name in names:
        if name in group.variables:
            return name
        if name.lower() in vars_lower:
            return vars_lower[name.lower()]
    return None


def canonical_field(group: Any, requested: str) -> Optional[str]:
    requested = requested.strip()
    if requested in group.variables:
        return requested
    for canonical, aliases in FIELD_ALIASES.items():
        if requested.upper() == canonical or requested.lower() in [a.lower() for a in aliases]:
            found = first_existing_var(group, aliases)
            if found:
                return found
    # Final forgiving match.
    vars_lower = {name.lower(): name for name in group.variables.keys()}
    return vars_lower.get(requested.lower())


def choose_sweep(ds: Any, sweep_name: Optional[str], sweep_index: int) -> Tuple[str, Any]:
    if sweep_name:
        if sweep_name not in ds.groups:
            raise SystemExit(f"Sweep group not found: {sweep_name}. Available: {list(ds.groups.keys())}")
        return sweep_name, ds.groups[sweep_name]

    sweep_groups = [(name, grp) for name, grp in ds.groups.items() if name.startswith("sweep_")]
    if not sweep_groups:
        raise SystemExit("No sweep_* groups found in CfRadial file.")
    sweep_groups.sort(key=lambda item: item[0])
    if sweep_index < 0 or sweep_index >= len(sweep_groups):
        raise SystemExit(f"Sweep index {sweep_index} out of range; available 0..{len(sweep_groups)-1}")
    return sweep_groups[sweep_index]


def read_coord(np: Any, group: Any, logical_name: str) -> Tuple[str, Any]:
    var_name = first_existing_var(group, COORD_ALIASES[logical_name])
    if not var_name:
        raise SystemExit(f"Required coordinate missing: {logical_name}. Variables: {list(group.variables.keys())}")
    return var_name, np.asarray(group.variables[var_name][:], dtype="float64")


def masked_data(np: Any, var: Any) -> Any:
    return masked_numeric_array(var)


def field_stats(np: Any, arr: Any, var: Any) -> Dict[str, Any]:
    finite = arr[np.isfinite(arr)]
    stats: Dict[str, Any] = {
        "source_variable": var.name,
        "shape": list(arr.shape),
        "dtype": str(var.dtype),
        "units": json_safe(getattr(var, "units", None)),
        "long_name": json_safe(getattr(var, "long_name", None)),
        "standard_name": json_safe(getattr(var, "standard_name", None)),
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


def color_ref(v: float) -> Tuple[int, int, int, int]:
    # Approximate NWS-style reflectivity ramp. Transparent below threshold.
    if not math.isfinite(v) or v < -10:
        return (0, 0, 0, 0)
    stops = [
        (-10, (0, 0, 0, 0)),
        (0, (4, 30, 130, 180)),
        (10, (25, 95, 220, 220)),
        (20, (55, 190, 70, 235)),
        (30, (245, 230, 65, 245)),
        (40, (245, 130, 35, 250)),
        (50, (220, 35, 35, 255)),
        (60, (175, 45, 170, 255)),
        (70, (245, 245, 245, 255)),
    ]
    return interp_stops(v, stops)


def color_vel(v: float, vmax: float) -> Tuple[int, int, int, int]:
    if not math.isfinite(v):
        return (0, 0, 0, 0)
    vmax = max(1.0, float(vmax))
    x = max(-1.0, min(1.0, v / vmax))
    if x < 0:
        # inbound-ish green/cyan
        t = abs(x)
        return (int(35 + 20 * (1 - t)), int(70 + 180 * t), int(80 + 50 * t), 245)
    if x > 0:
        # outbound-ish red/yellow
        t = x
        return (int(80 + 175 * t), int(70 + 50 * (1 - t)), int(40 + 20 * (1 - t)), 245)
    return (25, 25, 25, 100)


def color_sw(v: float) -> Tuple[int, int, int, int]:
    if not math.isfinite(v):
        return (0, 0, 0, 0)
    stops = [
        (0, (8, 8, 20, 80)),
        (2, (45, 70, 150, 180)),
        (5, (120, 70, 190, 230)),
        (10, (230, 110, 220, 250)),
        (20, (255, 240, 255, 255)),
    ]
    return interp_stops(v, stops)


def color_generic(v: float, vmin: float, vmax: float) -> Tuple[int, int, int, int]:
    if not math.isfinite(v):
        return (0, 0, 0, 0)
    if not math.isfinite(vmin) or not math.isfinite(vmax) or vmax <= vmin:
        return (200, 200, 200, 230)
    t = max(0.0, min(1.0, (v - vmin) / (vmax - vmin)))
    return (int(30 + 220 * t), int(60 + 100 * (1 - abs(t - 0.5) * 2)), int(220 - 200 * t), 235)


def interp_stops(v: float, stops: Sequence[Tuple[float, Tuple[int, int, int, int]]]) -> Tuple[int, int, int, int]:
    if v <= stops[0][0]:
        return stops[0][1]
    for (x0, c0), (x1, c1) in zip(stops[:-1], stops[1:]):
        if v <= x1:
            t = (v - x0) / (x1 - x0) if x1 != x0 else 0.0
            return tuple(int(c0[i] + (c1[i] - c0[i]) * t) for i in range(4))  # type: ignore
    return stops[-1][1]


def color_for(field_requested: str, value: float, vmin: float, vmax: float, nyquist: Optional[float]) -> Tuple[int, int, int, int]:
    f = field_requested.upper()
    if f in ("REF", "DBZ", "ZH"):
        return color_ref(value)
    if f in ("VEL", "VR", "V"):
        lim = nyquist if nyquist and nyquist > 0 else max(abs(vmin), abs(vmax), 1.0)
        return color_vel(value, lim)
    if f in ("SW", "WIDTH"):
        return color_sw(value)
    return color_generic(value, vmin, vmax)


def infer_range_km(range_values: Any, units: Optional[str]) -> Any:
    import numpy as np  # type: ignore

    rng = np.asarray(range_values, dtype="float64")
    units_l = (units or "").lower()
    if "km" in units_l or "kilometer" in units_l:
        return rng
    # CfRadial usually stores range in meters.
    return rng / 1000.0


def render_native_ppi(
    np: Any,
    Image: Any,
    ImageDraw: Any,
    arr: Any,
    az_deg: Any,
    range_km: Any,
    field_requested: str,
    stats: Dict[str, Any],
    out_png: Path,
    title: str,
    size: int,
    max_range_km: Optional[float],
    gate_stride: int,
    ray_stride: int,
    nyquist: Optional[float],
) -> Dict[str, Any]:
    """Render observed gates in native polar geometry onto a transparent plan view."""
    if arr.ndim != 2:
        raise SystemExit(f"Expected 2-D field array [ray, gate], got shape {arr.shape}")

    nrays, ngates = arr.shape
    if az_deg.shape[0] != nrays:
        raise SystemExit(f"Azimuth length {az_deg.shape[0]} does not match field ray count {nrays}")
    if range_km.shape[0] != ngates:
        # Some files include range as 2-D or off by metadata; fail honestly.
        raise SystemExit(f"Range length {range_km.shape[0]} does not match field gate count {ngates}")

    if max_range_km is None:
        max_range_km = float(np.nanmax(range_km))
    max_range_km = max(1.0, float(max_range_km))

    margin = 90
    center = size // 2
    scale = (size / 2 - margin) / max_range_km

    img = Image.new("RGBA", (size, size), (7, 10, 18, 255))
    draw = ImageDraw.Draw(img, "RGBA")

    # Range rings.
    ring_step = nice_ring_step(max_range_km)
    ring = ring_step
    while ring <= max_range_km + 0.001:
        rpx = ring * scale
        bbox = [center - rpx, center - rpx, center + rpx, center + rpx]
        draw.ellipse(bbox, outline=(70, 90, 120, 95), width=1)
        draw.text((center + rpx + 4, center - 8), f"{ring:g} km", fill=(150, 165, 190, 190))
        ring += ring_step

    # Cardinal axes.
    draw.line((center, margin // 2, center, size - margin // 2), fill=(80, 95, 120, 100), width=1)
    draw.line((margin // 2, center, size - margin // 2, center), fill=(80, 95, 120, 100), width=1)
    draw.text((center + 6, margin // 2), "N", fill=(180, 190, 210, 220))

    finite = arr[np.isfinite(arr)]
    vmin = float(np.nanmin(finite)) if finite.size else float("nan")
    vmax = float(np.nanmax(finite)) if finite.size else float("nan")

    # Draw observed gates. Point rendering is intentionally literal: no smoothing, no interpolation.
    point_radius = max(1, int(size / 1200))
    drawn = 0
    skipped_out_of_range = 0
    for ri in range(0, nrays, max(1, ray_stride)):
        az = math.radians(float(az_deg[ri]))
        sin_az = math.sin(az)
        cos_az = math.cos(az)
        row = arr[ri]
        for gi in range(0, ngates, max(1, gate_stride)):
            rkm = float(range_km[gi])
            if rkm > max_range_km:
                skipped_out_of_range += 1
                continue
            value = float(row[gi])
            color = color_for(field_requested, value, vmin, vmax, nyquist)
            if color[3] == 0:
                continue
            # Meteorological convention: azimuth degrees clockwise from north.
            x = center + rkm * scale * sin_az
            y = center - rkm * scale * cos_az
            if point_radius <= 1:
                draw.point((x, y), fill=color)
            else:
                draw.rectangle((x - point_radius, y - point_radius, x + point_radius, y + point_radius), fill=color)
            drawn += 1

    # Title/provenance panel.
    panel_h = 70
    draw.rectangle((0, 0, size, panel_h), fill=(7, 10, 18, 235))
    draw.text((16, 12), title, fill=(235, 240, 250, 255))
    subtitle = (
        f"Native polar gate preview; observed gates only; no gridding/interpolation | "
        f"rays={nrays} gates={ngates} drawn={drawn} stride(ray={ray_stride}, gate={gate_stride})"
    )
    draw.text((16, 38), subtitle, fill=(175, 190, 210, 230))

    # Legend.
    legend_w = 360
    legend_h = 50
    lx = size - legend_w - 18
    ly = size - legend_h - 18
    draw.rectangle((lx - 10, ly - 12, lx + legend_w + 10, ly + legend_h + 10), fill=(7, 10, 18, 220))
    for i in range(legend_w):
        if field_requested.upper() in ("REF", "DBZ", "ZH"):
            val = -10 + 80 * i / (legend_w - 1)
        elif field_requested.upper() in ("VEL", "VR", "V"):
            lim = nyquist if nyquist and nyquist > 0 else max(abs(vmin), abs(vmax), 1.0)
            val = -lim + 2 * lim * i / (legend_w - 1)
        elif field_requested.upper() in ("SW", "WIDTH"):
            val = 20 * i / (legend_w - 1)
        else:
            val = vmin + (vmax - vmin) * i / (legend_w - 1) if math.isfinite(vmin + vmax) else 0
        draw.line((lx + i, ly, lx + i, ly + 16), fill=color_for(field_requested, val, vmin, vmax, nyquist))
    units = stats.get("units") or ""
    draw.text((lx, ly + 22), f"{field_requested} {units} | min={stats.get('min')} max={stats.get('max')}", fill=(210, 220, 235, 230))

    out_png.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_png)
    return {
        "png": str(out_png),
        "render_type": "native_polar_ppi_observed_gates_only",
        "image_size_px": [size, size],
        "max_range_km": max_range_km,
        "drawn_gate_samples": drawn,
        "skipped_out_of_range_samples": skipped_out_of_range,
        "ray_stride": ray_stride,
        "gate_stride": gate_stride,
        "note": "This is a preview/verification image, not a gridded 3D product.",
    }


def nice_ring_step(max_range_km: float) -> float:
    candidates = [5, 10, 20, 25, 50, 100, 150, 200]
    target = max_range_km / 5.0
    return min(candidates, key=lambda c: abs(c - target))


def convert_cfile_if_needed(input_path: Path, out_dir: Path) -> Tuple[Path, Optional[Path]]:
    suffix = input_path.suffix.lower()
    if suffix not in (".cfl", ".cfile"):
        return input_path, None
    converter = shutil.which("cfile_to_cfradial")
    if not converter:
        raise SystemExit("Input is CFILE but cfile_to_cfradial was not found in PATH.")
    convert_dir = out_dir / "converted_cfradial"
    convert_dir.mkdir(parents=True, exist_ok=True)
    before = set(convert_dir.glob("*.nc"))
    cmd = [converter, str(input_path), str(convert_dir)]
    print("Converting CFILE to CfRadial:", " ".join(cmd), file=sys.stderr)
    subprocess.run(cmd, check=True)
    after = set(convert_dir.glob("*.nc"))
    new_files = sorted(after - before, key=lambda p: p.stat().st_mtime, reverse=True)
    if not new_files:
        # Some converters overwrite or use fixed names; choose newest .nc.
        new_files = sorted(after, key=lambda p: p.stat().st_mtime, reverse=True)
    if not new_files:
        raise SystemExit(f"Converter completed but no .nc file found in {convert_dir}")
    return new_files[0], convert_dir


def build_manifest(ds: Any, nc_path: Path, input_path: Path, sweep_name: str, group: Any, coord_names: Dict[str, str]) -> Dict[str, Any]:
    attrs = {name: json_safe(getattr(ds, name)) for name in ds.ncattrs()}
    group_attrs = {name: json_safe(getattr(group, name)) for name in group.ncattrs()}
    return {
        "stormdeck_schema": "stormdeck.single_frame_preview.v0",
        "source_input": str(input_path),
        "source_nc": str(nc_path),
        "format_assumption": "CfRadial NetCDF with sweep_* groups",
        "scientific_status": "observed_native_radial_preview_not_gridded_not_interpolated",
        "netcdf_data_model": json_safe(getattr(ds, "data_model", None)),
        "global_attributes": attrs,
        "sweep": {
            "name": sweep_name,
            "dimensions": {name: len(dim) for name, dim in group.dimensions.items()},
            "attributes": group_attrs,
            "coordinate_variables": coord_names,
            "available_variables": list(group.variables.keys()),
        },
        "fields": {},
        "renders": [],
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Render a single native polar quicklook PNG from one CfRadial/CFILE frame."
    )
    parser.add_argument("input", help="Input .nc CfRadial file, or .cfl CFILE if cfile_to_cfradial is available")
    parser.add_argument("--out", default="stormdeck_single_frame_preview", help="Output directory")
    parser.add_argument("--field", default="REF", help="Field to render, e.g. REF, VEL, SW. Use --all-default-fields for REF/VEL/SW.")
    parser.add_argument("--all-default-fields", action="store_true", help="Render REF, VEL, and SW if present")
    parser.add_argument("--sweep", default=None, help="Sweep group name, e.g. sweep_0")
    parser.add_argument("--sweep-index", type=int, default=0, help="Sweep index if --sweep is omitted")
    parser.add_argument("--size", type=int, default=1600, help="Square output image size in pixels")
    parser.add_argument("--max-range-km", type=float, default=None, help="Clip preview to range in km")
    parser.add_argument("--gate-stride", type=int, default=1, help="Draw every Nth gate for speed")
    parser.add_argument("--ray-stride", type=int, default=1, help="Draw every Nth ray for speed")
    args = parser.parse_args(argv)

    np, Dataset, Image, ImageDraw = _require_runtime_deps()

    input_path = Path(args.input).expanduser().resolve()
    out_dir = Path(args.out).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    nc_path, convert_dir = convert_cfile_if_needed(input_path, out_dir)

    ds = Dataset(str(nc_path), "r")
    try:
        sweep_name, group = choose_sweep(ds, args.sweep, args.sweep_index)

        range_var_name, range_values = read_coord(np, group, "range")
        az_var_name, az_deg = read_coord(np, group, "azimuth")
        el_var_name, el_deg = read_coord(np, group, "elevation")
        range_units = json_safe(getattr(group.variables[range_var_name], "units", "meters"))
        range_km = infer_range_km(range_values, range_units)

        coord_names = {"range": range_var_name, "azimuth": az_var_name, "elevation": el_var_name}
        time_name = first_existing_var(group, COORD_ALIASES["time"])
        if time_name:
            coord_names["time"] = time_name
        nyq_name = first_existing_var(group, COORD_ALIASES["nyquist_velocity"])
        if nyq_name:
            coord_names["nyquist_velocity"] = nyq_name

        manifest = build_manifest(ds, nc_path, input_path, sweep_name, group, coord_names)
        if convert_dir:
            manifest["conversion"] = {"tool": "cfile_to_cfradial", "output_dir": str(convert_dir)}

        nyquist: Optional[float] = None
        if nyq_name:
            nyq_values = np.asarray(group.variables[nyq_name][:], dtype="float64")
            finite_nyq = nyq_values[np.isfinite(nyq_values)]
            if finite_nyq.size:
                nyquist = float(np.nanmedian(finite_nyq))

        requested_fields = ["REF", "VEL", "SW"] if args.all_default_fields else [args.field]
        rendered_any = False
        missing: List[str] = []

        for requested in requested_fields:
            var_name = canonical_field(group, requested)
            if not var_name:
                missing.append(requested)
                continue
            var = group.variables[var_name]
            arr = masked_data(np, var)
            stats = field_stats(np, arr, var)
            stats["requested_field"] = requested
            manifest["fields"][requested] = stats

            title_bits = [f"StormDeck single-frame preview", f"field={requested}({var_name})", f"sweep={sweep_name}"]
            for attr_name in ("instrument_name", "site_name", "scan_name", "time_coverage_start"):
                if hasattr(ds, attr_name):
                    title_bits.append(f"{attr_name}={json_safe(getattr(ds, attr_name))}")
            title = " | ".join(title_bits)

            out_png = out_dir / f"quicklook_{requested}_{sweep_name}.png"
            render_info = render_native_ppi(
                np=np,
                Image=Image,
                ImageDraw=ImageDraw,
                arr=arr,
                az_deg=az_deg,
                range_km=range_km,
                field_requested=requested,
                stats=stats,
                out_png=out_png,
                title=title,
                size=args.size,
                max_range_km=args.max_range_km,
                gate_stride=max(1, args.gate_stride),
                ray_stride=max(1, args.ray_stride),
                nyquist=nyquist,
            )
            manifest["renders"].append(render_info)
            rendered_any = True

        manifest["missing_requested_fields"] = missing
        manifest_path = out_dir / "frame_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

        if not rendered_any:
            print(json.dumps(manifest, indent=2, sort_keys=True))
            raise SystemExit(f"None of requested fields were present: {requested_fields}")

        print(f"Wrote manifest: {manifest_path}")
        for render in manifest["renders"]:
            print(f"Wrote PNG: {render['png']}")
        if missing:
            print(f"Missing fields skipped: {', '.join(missing)}", file=sys.stderr)
        return 0
    finally:
        ds.close()


if __name__ == "__main__":
    raise SystemExit(main())
