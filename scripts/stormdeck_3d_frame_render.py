#!/usr/bin/env python3
"""
StormDeck actual-data single-frame 3D renderer.

This renders one CfRadial/CFILE radar frame as an oblique 3D point/voxel image
using the actual source gate geometry:

    range + azimuth + elevation + field value -> local x/y/z gate positions -> PNG

It is intentionally dependency-light for wea-fs:
- numpy
- netCDF4
- Pillow

It is not a game-engine renderer yet. It is the first reproducible bridge from
real KATD/ATD radar data to a 3D frame we can inspect before building Godot/WebGPU.
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


def require_deps() -> Tuple[Any, Any, Any, Any]:
    try:
        import numpy as np  # type: ignore
        from netCDF4 import Dataset  # type: ignore
        from PIL import Image, ImageDraw  # type: ignore
    except Exception:
        print(
            "Missing dependency. On wea-fs: sudo dnf install python3-numpy python3-netcdf4 python3-pillow",
            file=sys.stderr,
        )
        raise
    return np, Dataset, Image, ImageDraw


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
    if isinstance(value, (str, int, float, bool)) or value is None:
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
    if requested in group.variables:
        return requested
    requested_l = requested.lower()
    requested_u = requested.upper()
    for canonical, aliases in FIELD_ALIASES.items():
        if requested_u == canonical or requested_l in [a.lower() for a in aliases]:
            found = first_existing_var(group, aliases)
            if found:
                return found
    lower = {name.lower(): name for name in group.variables.keys()}
    return lower.get(requested_l)


def choose_sweep(ds: Any, sweep_name: Optional[str], sweep_index: int) -> Tuple[str, Any]:
    if sweep_name:
        if sweep_name not in ds.groups:
            raise SystemExit(f"Sweep not found: {sweep_name}; available={list(ds.groups.keys())}")
        return sweep_name, ds.groups[sweep_name]
    sweeps = sorted((name, group) for name, group in ds.groups.items() if name.startswith("sweep_"))
    if not sweeps:
        raise SystemExit("No sweep_* groups found. This script expects grouped CfRadial output.")
    if sweep_index < 0 or sweep_index >= len(sweeps):
        raise SystemExit(f"Sweep index {sweep_index} out of range 0..{len(sweeps)-1}")
    return sweeps[sweep_index]


def read_coord(np: Any, group: Any, logical_name: str) -> Tuple[str, Any]:
    name = first_existing_var(group, COORD_ALIASES[logical_name])
    if not name:
        raise SystemExit(f"Missing coordinate {logical_name}; variables={list(group.variables.keys())}")
    return name, np.asarray(group.variables[name][:], dtype="float64")


def infer_range_km(range_values: Any, units: Optional[str]) -> Any:
    import numpy as np  # type: ignore

    rng = np.asarray(range_values, dtype="float64")
    units_l = (units or "").lower()
    if "km" in units_l or "kilometer" in units_l:
        return rng
    return rng / 1000.0


def masked_data(np: Any, var: Any) -> Any:
    arr = var[:]
    if np.ma.isMaskedArray(arr):
        out = arr.astype("float64").filled(np.nan)
    else:
        out = np.asarray(arr, dtype="float64")
        fill = getattr(var, "_FillValue", None)
        if fill is not None:
            out[out == fill] = np.nan
    out[out <= -9990] = np.nan
    return out


def convert_cfile_if_needed(input_path: Path, out_dir: Path) -> Tuple[Path, Optional[Path]]:
    if input_path.suffix.lower() not in (".cfl", ".cfile"):
        return input_path, None
    converter = shutil.which("cfile_to_cfradial")
    if not converter:
        raise SystemExit("Input is CFILE but cfile_to_cfradial is not in PATH.")
    convert_dir = out_dir / "converted_cfradial"
    convert_dir.mkdir(parents=True, exist_ok=True)
    before = set(convert_dir.glob("*.nc"))
    cmd = [converter, str(input_path), str(convert_dir)]
    print("Converting CFILE:", " ".join(cmd), file=sys.stderr)
    subprocess.run(cmd, check=True)
    after = set(convert_dir.glob("*.nc"))
    new_files = sorted(after - before, key=lambda p: p.stat().st_mtime, reverse=True)
    if not new_files:
        new_files = sorted(after, key=lambda p: p.stat().st_mtime, reverse=True)
    if not new_files:
        raise SystemExit(f"No converted .nc found in {convert_dir}")
    return new_files[0], convert_dir


def interp_stops(v: float, stops: Sequence[Tuple[float, Tuple[int, int, int, int]]]) -> Tuple[int, int, int, int]:
    if not math.isfinite(v) or v <= stops[0][0]:
        return stops[0][1]
    for (x0, c0), (x1, c1) in zip(stops[:-1], stops[1:]):
        if v <= x1:
            t = (v - x0) / (x1 - x0) if x1 != x0 else 0.0
            return tuple(int(c0[i] + (c1[i] - c0[i]) * t) for i in range(4))  # type: ignore
    return stops[-1][1]


def color_ref(v: float) -> Tuple[int, int, int, int]:
    return interp_stops(
        v,
        [
            (-10.0, (0, 0, 0, 0)),
            (0.0, (4, 30, 130, 100)),
            (10.0, (25, 95, 220, 150)),
            (20.0, (55, 190, 70, 190)),
            (30.0, (245, 230, 65, 215)),
            (40.0, (245, 130, 35, 235)),
            (50.0, (220, 35, 35, 245)),
            (60.0, (175, 45, 170, 255)),
            (70.0, (245, 245, 245, 255)),
        ],
    )


def color_vel(v: float, vmax: float) -> Tuple[int, int, int, int]:
    if not math.isfinite(v):
        return (0, 0, 0, 0)
    vmax = max(1.0, vmax)
    x = max(-1.0, min(1.0, v / vmax))
    if x < 0:
        t = -x
        return (int(35 + 25 * (1 - t)), int(80 + 175 * t), int(80 + 60 * t), 215)
    t = x
    return (int(95 + 155 * t), int(80 + 40 * (1 - t)), int(40 + 20 * (1 - t)), 215)


def color_sw(v: float) -> Tuple[int, int, int, int]:
    return interp_stops(
        v,
        [
            (0.0, (12, 12, 35, 70)),
            (2.0, (45, 70, 150, 140)),
            (5.0, (120, 70, 190, 190)),
            (10.0, (230, 110, 220, 230)),
            (20.0, (255, 240, 255, 255)),
        ],
    )


def color_generic(v: float, vmin: float, vmax: float) -> Tuple[int, int, int, int]:
    if not math.isfinite(v) or vmax <= vmin:
        return (0, 0, 0, 0)
    t = max(0.0, min(1.0, (v - vmin) / (vmax - vmin)))
    return (int(35 + 220 * t), int(90 + 100 * (1 - abs(t - 0.5) * 2)), int(230 - 210 * t), 210)


def color_for(field: str, value: float, vmin: float, vmax: float, nyquist: Optional[float]) -> Tuple[int, int, int, int]:
    f = field.upper()
    if f in ("REF", "DBZ", "ZH"):
        return color_ref(value)
    if f in ("VEL", "VR", "V"):
        lim = nyquist if nyquist and nyquist > 0 else max(abs(vmin), abs(vmax), 1.0)
        return color_vel(value, lim)
    if f in ("SW", "WIDTH"):
        return color_sw(value)
    return color_generic(value, vmin, vmax)


def field_stats(np: Any, arr: Any, var: Any) -> Dict[str, Any]:
    finite = arr[np.isfinite(arr)]
    out: Dict[str, Any] = {
        "source_variable": var.name,
        "shape": list(arr.shape),
        "dtype": str(var.dtype),
        "units": json_safe(getattr(var, "units", None)),
        "long_name": json_safe(getattr(var, "long_name", None)),
        "valid_gate_count": int(finite.size),
        "missing_gate_count": int(arr.size - finite.size),
    }
    if finite.size:
        out.update(
            {
                "min": float(np.nanmin(finite)),
                "max": float(np.nanmax(finite)),
                "mean": float(np.nanmean(finite)),
                "p01": float(np.nanpercentile(finite, 1)),
                "p50": float(np.nanpercentile(finite, 50)),
                "p99": float(np.nanpercentile(finite, 99)),
            }
        )
    return out


def gate_xyz(np: Any, range_km: Any, az_deg: Any, el_deg: Any) -> Tuple[Any, Any, Any]:
    """Return local Cartesian gate coordinates in km: x=east, y=north, z=up."""
    az = np.deg2rad(az_deg).reshape((-1, 1))
    el = np.deg2rad(el_deg).reshape((-1, 1))
    r = range_km.reshape((1, -1))
    ground = r * np.cos(el)
    x = ground * np.sin(az)
    y = ground * np.cos(az)
    z = r * np.sin(el)
    return x, y, z


def camera_vectors(np: Any, yaw_deg: float, pitch_deg: float) -> Tuple[Any, Any, Any]:
    """Simple oblique orthographic camera basis looking toward origin."""
    yaw = math.radians(yaw_deg)
    pitch = math.radians(pitch_deg)
    # Camera looks from direction d toward origin.
    forward = np.asarray(
        [math.sin(yaw) * math.cos(pitch), math.cos(yaw) * math.cos(pitch), math.sin(pitch)],
        dtype="float64",
    )
    forward = forward / np.linalg.norm(forward)
    up_world = np.asarray([0.0, 0.0, 1.0], dtype="float64")
    right = np.cross(forward, up_world)
    if np.linalg.norm(right) < 1e-6:
        right = np.asarray([1.0, 0.0, 0.0])
    right = right / np.linalg.norm(right)
    up = np.cross(right, forward)
    up = up / np.linalg.norm(up)
    return right, up, forward


def project_points(np: Any, x: Any, y: Any, z: Any, right: Any, up: Any, forward: Any) -> Tuple[Any, Any, Any]:
    sx = x * right[0] + y * right[1] + z * right[2]
    sy = x * up[0] + y * up[1] + z * up[2]
    depth = x * forward[0] + y * forward[1] + z * forward[2]
    return sx, sy, depth


def blend_pixel(img: Any, x: int, y: int, color: Tuple[int, int, int, int]) -> None:
    if x < 0 or y < 0 or x >= img.width or y >= img.height:
        return
    src_a = color[3] / 255.0
    if src_a <= 0:
        return
    dst = img.getpixel((x, y))
    out = (
        int(color[0] * src_a + dst[0] * (1 - src_a)),
        int(color[1] * src_a + dst[1] * (1 - src_a)),
        int(color[2] * src_a + dst[2] * (1 - src_a)),
        255,
    )
    img.putpixel((x, y), out)


def draw_dot(img: Any, x: int, y: int, color: Tuple[int, int, int, int], radius: int) -> None:
    if radius <= 1:
        blend_pixel(img, x, y, color)
        return
    rr = radius * radius
    for yy in range(y - radius, y + radius + 1):
        for xx in range(x - radius, x + radius + 1):
            if (xx - x) * (xx - x) + (yy - y) * (yy - y) <= rr:
                blend_pixel(img, xx, yy, color)


def draw_projected_polyline(draw: Any, pts: List[Tuple[float, float, float]], basis: Tuple[Any, Any, Any], scale: float, cx: int, cy: int, color: Tuple[int, int, int, int], width: int = 1) -> None:
    import numpy as np  # type: ignore

    right, up, forward = basis
    pix: List[Tuple[int, int]] = []
    for x, y, z in pts:
        p = np.asarray([x, y, z], dtype="float64")
        sx = float(np.dot(p, right))
        sy = float(np.dot(p, up))
        pix.append((int(cx + sx * scale), int(cy - sy * scale)))
    if len(pix) > 1:
        draw.line(pix, fill=color, width=width)


def draw_scene_guides(np: Any, draw: Any, basis: Tuple[Any, Any, Any], scale: float, cx: int, cy: int, max_range_km: float) -> None:
    # Ground range rings projected into the oblique camera.
    for ring in nice_rings(max_range_km):
        pts = []
        for k in range(145):
            th = 2 * math.pi * k / 144
            pts.append((ring * math.sin(th), ring * math.cos(th), 0.0))
        draw_projected_polyline(draw, pts, basis, scale, cx, cy, (70, 90, 120, 90), 1)
    # East and north axes.
    draw_projected_polyline(draw, [(-max_range_km, 0, 0), (max_range_km, 0, 0)], basis, scale, cx, cy, (85, 95, 115, 95), 1)
    draw_projected_polyline(draw, [(0, -max_range_km, 0), (0, max_range_km, 0)], basis, scale, cx, cy, (85, 95, 115, 95), 1)
    # Vertical height pole at radar origin.
    draw_projected_polyline(draw, [(0, 0, 0), (0, 0, 20)], basis, scale, cx, cy, (130, 150, 180, 140), 2)


def nice_rings(max_range_km: float) -> List[float]:
    if max_range_km <= 60:
        step = 10
    elif max_range_km <= 140:
        step = 20
    else:
        step = 50
    rings: List[float] = []
    r = step
    while r <= max_range_km + 0.001:
        rings.append(float(r))
        r += step
    return rings


def render_3d_frame(
    np: Any,
    Image: Any,
    ImageDraw: Any,
    arr: Any,
    x: Any,
    y: Any,
    z: Any,
    field: str,
    stats: Dict[str, Any],
    out_png: Path,
    title: str,
    width: int,
    height: int,
    yaw: float,
    pitch: float,
    max_range_km: float,
    max_height_km: float,
    threshold: Optional[float],
    gate_stride: int,
    ray_stride: int,
    dot_radius: int,
    nyquist: Optional[float],
) -> Dict[str, Any]:
    img = Image.new("RGBA", (width, height), (7, 10, 18, 255))
    draw = ImageDraw.Draw(img, "RGBA")

    right, up, forward = camera_vectors(np, yaw, pitch)
    sx, sy, depth = project_points(np, x, y, z, right, up, forward)

    finite = arr[np.isfinite(arr)]
    if not finite.size:
        raise SystemExit("Selected field contains no finite values.")
    vmin = float(np.nanmin(finite))
    vmax = float(np.nanmax(finite))

    if threshold is None:
        threshold = 5.0 if field.upper() in ("REF", "DBZ", "ZH") else float(np.nanpercentile(finite, 60))

    # Scale by requested max range and a little headroom for height.
    scene_half_span = max(max_range_km, 20.0)
    scale = min(width * 0.78 / (2 * scene_half_span), height * 0.72 / (scene_half_span + max_height_km))
    cx = width // 2
    cy = int(height * 0.66)

    draw_scene_guides(np, draw, (right, up, forward), scale, cx, cy, max_range_km)

    # Build sampled point list from actual gates. Sort far-to-near for alpha compositing.
    points: List[Tuple[float, int, int, float]] = []
    nrays, ngates = arr.shape
    for ri in range(0, nrays, max(1, ray_stride)):
        for gi in range(0, ngates, max(1, gate_stride)):
            value = float(arr[ri, gi])
            if not math.isfinite(value) or value < threshold:
                continue
            if float(z[ri, gi]) > max_height_km:
                continue
            rng = math.hypot(float(x[ri, gi]), float(y[ri, gi]))
            if rng > max_range_km:
                continue
            px = int(cx + float(sx[ri, gi]) * scale)
            py = int(cy - float(sy[ri, gi]) * scale)
            points.append((float(depth[ri, gi]), px, py, value))

    points.sort(key=lambda item: item[0])
    for _, px, py, value in points:
        color = color_for(field, value, vmin, vmax, nyquist)
        draw_dot(img, px, py, color, dot_radius)

    # HUD/provenance overlay.
    draw.rectangle((0, 0, width, 96), fill=(5, 8, 14, 235))
    draw.text((18, 14), title, fill=(238, 243, 252, 255))
    draw.text(
        (18, 42),
        "Actual radar gates rendered in 3D from range/azimuth/elevation. No gridding, no invented unsampled sectors.",
        fill=(180, 197, 220, 235),
    )
    draw.text(
        (18, 68),
        f"field={field} threshold={threshold:g} rays={nrays} gates={ngates} plotted={len(points)} stride(ray={ray_stride},gate={gate_stride})",
        fill=(156, 174, 205, 230),
    )

    # Small legend gradient.
    lx = width - 430
    ly = height - 70
    lw = 360
    draw.rectangle((lx - 12, ly - 16, lx + lw + 16, ly + 48), fill=(5, 8, 14, 215))
    for i in range(lw):
        if field.upper() in ("REF", "DBZ", "ZH"):
            vv = -10 + 80 * i / (lw - 1)
        elif field.upper() in ("VEL", "VR", "V"):
            lim = nyquist if nyquist and nyquist > 0 else max(abs(vmin), abs(vmax), 1.0)
            vv = -lim + 2 * lim * i / (lw - 1)
        elif field.upper() in ("SW", "WIDTH"):
            vv = 20 * i / (lw - 1)
        else:
            vv = vmin + (vmax - vmin) * i / (lw - 1)
        draw.line((lx + i, ly, lx + i, ly + 18), fill=color_for(field, vv, vmin, vmax, nyquist))
    units = stats.get("units") or ""
    draw.text((lx, ly + 25), f"{field} {units} | min={vmin:.2f} max={vmax:.2f}", fill=(215, 225, 240, 235))

    out_png.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_png)
    return {
        "png": str(out_png),
        "render_type": "actual_data_oblique_3d_gate_render",
        "projection": "local Cartesian x=east y=north z=up from source range/azimuth/elevation",
        "camera": {"yaw_deg": yaw, "pitch_deg": pitch, "orthographic": True},
        "image_size_px": [width, height],
        "max_range_km": max_range_km,
        "max_height_km": max_height_km,
        "threshold": threshold,
        "plotted_gate_samples": len(points),
        "ray_stride": ray_stride,
        "gate_stride": gate_stride,
        "dot_radius": dot_radius,
        "scientific_caveat": "3D observed-gate render. It is not gridded volume rendering and not meteorologically quality-controlled.",
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Render one actual CfRadial/CFILE radar frame as an oblique 3D gate PNG.")
    parser.add_argument("input", help="Input .nc CfRadial file, or .cfl CFILE if cfile_to_cfradial is available")
    parser.add_argument("--out", default="stormdeck_3d_frame", help="Output directory")
    parser.add_argument("--field", default="REF", help="Field to render, e.g. REF, VEL, SW")
    parser.add_argument("--sweep", default=None, help="Sweep group name, e.g. sweep_0")
    parser.add_argument("--sweep-index", type=int, default=0, help="Sweep index if --sweep is omitted")
    parser.add_argument("--width", type=int, default=1600, help="Output image width")
    parser.add_argument("--height", type=int, default=1000, help="Output image height")
    parser.add_argument("--yaw", type=float, default=135.0, help="Camera yaw degrees clockwise from north")
    parser.add_argument("--pitch", type=float, default=28.0, help="Camera pitch degrees above horizon")
    parser.add_argument("--max-range-km", type=float, default=90.0, help="Maximum ground range to render")
    parser.add_argument("--max-height-km", type=float, default=20.0, help="Maximum height to render")
    parser.add_argument("--threshold", type=float, default=None, help="Minimum field value to render; default is field-aware")
    parser.add_argument("--gate-stride", type=int, default=2, help="Sample every Nth gate")
    parser.add_argument("--ray-stride", type=int, default=1, help="Sample every Nth ray")
    parser.add_argument("--dot-radius", type=int, default=2, help="Rendered gate dot radius in pixels")
    args = parser.parse_args(argv)

    np, Dataset, Image, ImageDraw = require_deps()

    input_path = Path(args.input).expanduser().resolve()
    out_dir = Path(args.out).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    nc_path, convert_dir = convert_cfile_if_needed(input_path, out_dir)

    ds = Dataset(str(nc_path), "r")
    try:
        sweep_name, group = choose_sweep(ds, args.sweep, args.sweep_index)
        field_var_name = canonical_field(group, args.field)
        if not field_var_name:
            raise SystemExit(f"Field {args.field} not found in {sweep_name}; variables={list(group.variables.keys())}")

        range_name, range_values = read_coord(np, group, "range")
        az_name, az_deg = read_coord(np, group, "azimuth")
        el_name, el_deg = read_coord(np, group, "elevation")
        range_units = json_safe(getattr(group.variables[range_name], "units", "meters"))
        range_km = infer_range_km(range_values, range_units)

        var = group.variables[field_var_name]
        arr = masked_data(np, var)
        if arr.ndim != 2:
            raise SystemExit(f"Expected 2-D field [ray, gate], got {arr.shape}")
        if len(az_deg) != arr.shape[0] or len(el_deg) != arr.shape[0] or len(range_km) != arr.shape[1]:
            raise SystemExit(
                "Coordinate/field shape mismatch: "
                f"field={arr.shape} az={len(az_deg)} el={len(el_deg)} range={len(range_km)}"
            )

        x, y, z = gate_xyz(np, range_km, az_deg, el_deg)
        stats = field_stats(np, arr, var)

        nyquist = None
        nyq_name = first_existing_var(group, COORD_ALIASES["nyquist_velocity"])
        if nyq_name:
            nyq = np.asarray(group.variables[nyq_name][:], dtype="float64")
            finite_nyq = nyq[np.isfinite(nyq)]
            if finite_nyq.size:
                nyquist = float(np.nanmedian(finite_nyq))

        title_parts = ["StormDeck actual-data 3D frame", f"field={args.field}({field_var_name})", f"sweep={sweep_name}"]
        for attr_name in ("instrument_name", "site_name", "time_coverage_start"):
            if hasattr(ds, attr_name):
                title_parts.append(f"{attr_name}={json_safe(getattr(ds, attr_name))}")
        title = " | ".join(title_parts)

        out_png = out_dir / f"3d_{args.field}_{sweep_name}.png"
        render_info = render_3d_frame(
            np=np,
            Image=Image,
            ImageDraw=ImageDraw,
            arr=arr,
            x=x,
            y=y,
            z=z,
            field=args.field,
            stats=stats,
            out_png=out_png,
            title=title,
            width=args.width,
            height=args.height,
            yaw=args.yaw,
            pitch=args.pitch,
            max_range_km=args.max_range_km,
            max_height_km=args.max_height_km,
            threshold=args.threshold,
            gate_stride=max(1, args.gate_stride),
            ray_stride=max(1, args.ray_stride),
            dot_radius=max(1, args.dot_radius),
            nyquist=nyquist,
        )

        manifest = {
            "stormdeck_schema": "stormdeck.actual_data_3d_frame.v0",
            "source_input": str(input_path),
            "source_nc": str(nc_path),
            "format_assumption": "CfRadial NetCDF with sweep_* groups",
            "scientific_status": "actual_radar_gate_3d_render_not_gridded_not_interpolated",
            "global_attributes": {name: json_safe(getattr(ds, name)) for name in ds.ncattrs()},
            "sweep": {
                "name": sweep_name,
                "dimensions": {name: len(dim) for name, dim in group.dimensions.items()},
                "coordinate_variables": {"range": range_name, "azimuth": az_name, "elevation": el_name},
                "available_variables": list(group.variables.keys()),
            },
            "field": stats,
            "render": render_info,
        }
        if convert_dir:
            manifest["conversion"] = {"tool": "cfile_to_cfradial", "output_dir": str(convert_dir)}

        manifest_path = out_dir / f"3d_{args.field}_{sweep_name}_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
        print(f"Wrote PNG: {out_png}")
        print(f"Wrote manifest: {manifest_path}")
        return 0
    finally:
        ds.close()


if __name__ == "__main__":
    raise SystemExit(main())
