# StormDeck Actual-Data 3D Frame Render

This is the next step after the 2D source-verification quicklook: render one **actual KATD/ATD radar frame** as an oblique 3D image using the source gate geometry.

This is **not** an AI concept mockup and not synthetic art. The renderer projects real radar gates:

```text
range + azimuth + elevation + field value
  -> local Cartesian x/y/z gate positions
  -> oblique camera projection
  -> PNG frame + JSON manifest
```

It is still not the final Godot/WebGPU cockpit. It is a dependency-light, reproducible CPU renderer that can run on `wea-fs` now.

## Script

```text
scripts/stormdeck_3d_frame_render.py
```

## What it renders

- Actual observed radar gates only.
- Local Cartesian coordinates:
  - `x`: east/west km from radar
  - `y`: north/south km from radar
  - `z`: height km from radar from elevation angle
- Oblique orthographic camera view.
- Ground range rings and vertical height pole.
- Reflectivity, velocity, spectrum width, or another selected field.
- HUD/provenance overlay explaining that this is actual gate geometry and not gridded/interpolated data.

## What it does not do yet

- No terrain or map tile alignment.
- No real warning polygon overlay.
- No storm-object detection.
- No interpolation or gridded volume fill.
- No multi-frame animation.
- No GPU/game-engine rendering.

That is intentional. This is the first actual-data 3D frame, not the full cockpit.

## Dependencies on `wea-fs`

Validated in the group transcript:

```bash
sudo dnf install python3-numpy python3-netcdf4 python3-pillow
```

Verify:

```bash
python3 - <<'PY'
import numpy, netCDF4
from PIL import Image
print('numpy', numpy.__version__)
print('netCDF4', netCDF4.__version__)
print('Pillow OK')
PY
```

## Recommended first run

From the known case directory:

```text
/atd15/scratch/data/ATD/2026/0521/141544/LVL2/CFILE
```

If the converted `.nc` exists:

```bash
python3 /path/to/StormDeck/scripts/stormdeck_3d_frame_render.py \
  KATD_Base_Data_20260521_141544_151077700.nc \
  --out /data/stormdeck/exports/KATD_20260521_141544/actual_3d_frame \
  --field REF \
  --sweep-index 0 \
  --width 1600 \
  --height 1000 \
  --max-range-km 90 \
  --max-height-km 20 \
  --threshold 10 \
  --gate-stride 2 \
  --ray-stride 1 \
  --dot-radius 2
```

If starting from CFILE:

```bash
python3 /path/to/StormDeck/scripts/stormdeck_3d_frame_render.py \
  KATD_Base_Data_20260521_141544_151077700.cfl \
  --out /data/stormdeck/exports/KATD_20260521_141544/actual_3d_frame \
  --field REF \
  --sweep-index 0 \
  --width 1600 \
  --height 1000 \
  --max-range-km 90 \
  --max-height-km 20 \
  --threshold 10 \
  --gate-stride 2 \
  --ray-stride 1 \
  --dot-radius 2
```

Expected outputs:

```text
/data/stormdeck/exports/KATD_20260521_141544/actual_3d_frame/
  3d_REF_sweep_0.png
  3d_REF_sweep_0_manifest.json
```

## Camera tuning

Default camera:

```text
--yaw 135
--pitch 28
```

Try alternate views:

```bash
--yaw 90 --pitch 25
--yaw 180 --pitch 30
--yaw 135 --pitch 45
```

## Field examples

Reflectivity:

```bash
--field REF --threshold 10
```

Velocity:

```bash
--field VEL --threshold -9999
```

Spectrum width:

```bash
--field SW --threshold 1
```

For velocity, use a low threshold because negative inbound velocities are meaningful. The script uses the source `nyquist_velocity` if present for the diverging velocity color scale.

## Verification checklist

The first actual-data 3D frame passes if:

1. `3d_REF_sweep_0.png` exists.
2. `3d_REF_sweep_0_manifest.json` exists.
3. Manifest says:
   - `stormdeck.actual_data_3d_frame.v0`
   - `actual_radar_gate_3d_render_not_gridded_not_interpolated`
4. Image shows an oblique 3D point/voxel gate cloud, not a flat PPI.
5. Ground range rings and height pole are visible.
6. The gate cloud shape is plausible when compared against the native 2D quicklook.
7. No unsampled 360-degree space is filled in.
8. The plotted gate count is nonzero and reasonable.

## Suggested workflow

Run both scripts on the same input:

```bash
python3 /path/to/StormDeck/scripts/stormdeck_single_frame_preview.py \
  KATD_Base_Data_20260521_141544_151077700.nc \
  --out /data/stormdeck/exports/KATD_20260521_141544/source_check \
  --field REF \
  --sweep-index 0

python3 /path/to/StormDeck/scripts/stormdeck_3d_frame_render.py \
  KATD_Base_Data_20260521_141544_151077700.nc \
  --out /data/stormdeck/exports/KATD_20260521_141544/actual_3d_frame \
  --field REF \
  --sweep-index 0 \
  --threshold 10
```

Compare:

```text
source_check/quicklook_REF_sweep_0.png
actual_3d_frame/3d_REF_sweep_0.png
```

The 3D frame should be recognizably derived from the same sector/returns, just viewed obliquely with height from elevation angle.

## Next after this works

1. Render multiple sweeps into the same image if a volume contains more than one elevation.
2. Add a second field overlay, especially velocity near the reflectivity hook.
3. Export gate buffers for Godot/WebGPU:

```text
geometry/x.f32
geometry/y.f32
geometry/z.f32
fields/REF.f32
fields/VEL.f32
frame_manifest.json
```

4. Batch multiple frames into a PNG sequence.
5. Add HUD panels and warning/object overlays after the data geometry is trustworthy.
