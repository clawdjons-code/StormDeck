# StormDeck Single-Frame Preview Render

This is the first render/verification step for the KATD/ATD pipeline: produce a single-frame native-radial preview PNG from one converted CfRadial NetCDF file, or from one Level-2 CFILE if `cfile_to_cfradial` is available.

The goal is **source-file faithfulness before pretty 3D**. The preview renders observed radar gates in native polar geometry. It does not grid, interpolate, smooth, or invent unsampled space.

## Why this exists

From the PARtalk transcript, the current practical split is:

- `wea-fs`: backend/data/render-cache node.
  - RHEL 9.1
  - `/data` writable
  - 100 GbE on `172.16.1.30`
  - `numpy`, `netCDF4`, and `Pillow` available
  - `cfile_to_cfradial` available
- `sgregg`: restricted/static review client for now.
  - 1 GbE path to `wea-fs`
  - currently llvmpipe/software rendering, not usable for Godot 4/3D until IT enables GPU acceleration

So the first useful artifact should be a backend-generated PNG and manifest that Bryan/Stephen can inspect immediately.

## Script

```text
scripts/stormdeck_single_frame_preview.py
```

## Dependencies on `wea-fs`

Already validated or installed in the transcript:

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

## Recommended first run from the known CFILE directory

From:

```text
/atd15/scratch/data/ATD/2026/0521/141544/LVL2/CFILE
```

If the `.nc` already exists:

```bash
python3 /path/to/StormDeck/scripts/stormdeck_single_frame_preview.py \
  KATD_Base_Data_20260521_141544_151077700.nc \
  --out /data/stormdeck/exports/KATD_20260521_141544/single_frame \
  --all-default-fields \
  --sweep-index 0 \
  --size 1600
```

If starting from the `.cfl` file:

```bash
python3 /path/to/StormDeck/scripts/stormdeck_single_frame_preview.py \
  KATD_Base_Data_20260521_141544_151077700.cfl \
  --out /data/stormdeck/exports/KATD_20260521_141544/single_frame \
  --all-default-fields \
  --sweep-index 0 \
  --size 1600
```

The script will call `cfile_to_cfradial` for `.cfl` inputs.

## Expected outputs

```text
/data/stormdeck/exports/KATD_20260521_141544/single_frame/
  frame_manifest.json
  quicklook_REF_sweep_0.png
  quicklook_VEL_sweep_0.png
  quicklook_SW_sweep_0.png
  converted_cfradial/              # only if input was .cfl
```

If a requested field is missing, the script skips it and records that in `frame_manifest.json`.

## Fast/low-load run

For a quick smoke test, draw every fourth gate:

```bash
python3 /path/to/StormDeck/scripts/stormdeck_single_frame_preview.py \
  KATD_Base_Data_20260521_141544_151077700.nc \
  --out /data/stormdeck/exports/KATD_20260521_141544/smoke \
  --field REF \
  --gate-stride 4 \
  --size 1000
```

## Verification checklist

Pass criteria for the first frame:

1. `frame_manifest.json` exists and records:
   - source input
   - source NetCDF
   - sweep group
   - coordinate variable names
   - field stats
   - missing field list, if any
2. At least one PNG exists.
3. PNG title says:
   - native polar gate preview
   - observed gates only
   - no gridding/interpolation
4. The sector footprint looks like a sector, not a fake 360-degree radar.
5. Range rings and north/east axes are visible.
6. REF/VEL/SW values are plausible according to the manifest min/max/p99.

## Scientific caveats

- This is a **preview/verification image**, not a 3D StormDeck product.
- It preserves native polar/radial sampling and does not claim geospatial map alignment yet.
- It does not correct velocity folding, clutter, sidelobes, calibration issues, or attenuation.
- It should be compared against known/native tools before downstream gridding or volume rendering.

## Next step after this passes

Once Bryan verifies one frame visually, extend the same script family to export a render-cache frame:

```text
frame_manifest.json
geometry/range.f32
geometry/azimuth.f32
geometry/elevation.f32
fields/REF.f32
fields/VEL.f32
fields/SW.f32
quicklooks/*.png
```

That becomes the bridge into Godot/WebGPU once a true accelerated renderer machine is available.
