# StormDeck Backend System Architecture — Bryan/Stephen Scope

Last updated: 2026-05-21 18:18:24 CDT

Purpose: consolidate every available Bryan/Stephen PARtalk technical message into a backend-oriented StormDeck architecture document. This is the engineering scope for the data-local server, ingest pipeline, cache/API layer, and renderer-facing contracts. It is intentionally more backend-heavy than the public spec.

Source sessions inspected:

- Telegram PARtalk group, 2026-05-21.
- Hermes session `20260521_151547_55cb78f3` — Linux Deployment and Godot Design.
- Hermes session `20260521_172736_7b4692` — compacted continuation of the same thread.
- Hermes session `20260521_144626_ce95dfaf` / `20260521_174302_746b18` — group setup, Bryan quote, sample-data questions.
- Repo docs read: `docs/bryan-inputs.md`, `docs/atd-data-references.md`, `docs/conversation-digest-2026-05-21.md`.
- CFILE sample attachment path: `/Users/jonsclawdvandamn/.hermes/profiles/partner/cache/documents/doc_010a56869e71_sample-cfl-data.txt`.

Terminology note: Telegram showed direct technical messages from `Stephen Gregg`; Jon referred to this collaborator as Bryan/Brian in several prompts. This document treats those PARtalk collaborator messages as the Bryan/Stephen technical scope.

## 1. Executive backend decision

StormDeck should be built as a **data-local RHEL backend/cache/API system on `wea-fs` feeding a separate GPU renderer client**.

The backend must not be a thin afterthought. Bryan/Stephen's data reveals a serious radar-data environment:

- Internal NSSL/KATD Level 2 CFILE volume files are available on ATD scratch paths.
- CFILE can be converted to CfRadial NetCDF using installed tools.
- `wea-fs` has enough CPU, RAM, storage, Python, NetCDF, and 100 GbE networking to be the StormDeck data factory.
- `wea-fs` does **not** have a real rendering GPU; it only exposes ASPEED/BMC graphics.
- The MVP backend should use LVL2 CFILE -> CfRadial -> StormDeck canonical radial model -> render cache/API.
- LVL1/IQ is far too large for the first interactive path and belongs later.

Shortest honest architecture:

```text
ATD/KATD LVL2 CFILE on /atd15 and /data
  -> cfile_dump validation/provenance
  -> cfile_to_cfradial conversion
  -> Python netCDF4 reader
  -> StormDeck canonical radial/sweep/volume manifests
  -> quicklooks + render-ready cache
  -> FastAPI/static file API on wea-fs
  -> GPU renderer client, likely Godot/WebGPU, on separate workstation
```

## 2. Product/build-order guidance from Bryan

Bryan's initial product guidance remains valid and should be preserved as the project sequencing rule:

> Build an MWE first: an app using a game engine to render a 3D display of simulated reflectivity data, hard-coding as many parameters as necessary. Then feed more realistic archived data. Then wire up a live stream from an operational PAR.

Backend interpretation:

1. Synthetic MWE must still define the same metadata/data contract that real KATD ingest will use later.
2. Real-data backend can start in parallel, but it should not block the renderer MWE.
3. The first real-data target should be honest native/sector PPI rendering, not a fake full 3D storm cube.
4. Live PAR streaming is a future adapter after replay and cache contracts are stable.

## 3. Confirmed target backend host

### Host identity

Observed host prompts/commands reference:

```text
wea-fs.mpar.nssl
wea-fs
wea-fss
```

Backend spec should use `wea-fs` as the conceptual host and avoid depending on one exact hostname string until deployment config confirms it.

### OS/kernel

```text
Red Hat Enterprise Linux release 9.1 (Plow)
Linux 5.14.0-162.6.1.el9_1.x86_64
```

Design implications:

- Linux-first, RHEL-compatible.
- Prefer system packages and Python 3.9 compatibility.
- Avoid fragile desktop/runtime assumptions.
- Treat production install as closed/on-prem, not cloud-native by default.

### CPU/RAM

Observed:

- Dual Intel Xeon Silver 4316 @ 2.30 GHz.
- 2 sockets, 20 cores/socket, 40 physical cores, 80 logical CPUs.
- AVX2 and AVX-512 family support.
- About 502 GiB RAM.
- About 252 GiB `/dev/shm`.
- NUMA nodes: 2.

Backend implications:

- Very strong for CPU preprocessing, CfRadial conversion orchestration, indexing, manifests, quicklook generation, compression, gridding experiments, and multi-frame cache jobs.
- Large RAM supports case-level caching and batch processing.
- NUMA awareness may matter later for very large gridding jobs, but is not an MVP concern.

### GPU / rendering constraint

Observed graphics:

```text
ASPEED Technology AST2600 BMC/VGA
Kernel driver: ast
16 MB + 256 KB memory regions
```

Decision:

- `wea-fs` is **not** the interactive 3D renderer host.
- Do not run Godot/Unity/Unreal/WebGPU cockpit interactively on this box unless a real GPU is added.
- Use `wea-fs` as the StormDeck backend/data/state/cache server.
- Run the 4D renderer on a separate RTX/GTX-class workstation or future GPU node.

## 4. Storage topology and cache placement

Observed filesystems:

- `/`: 150G XFS, about 111G available.
- `/home`: 634G XFS, about 430G available.
- `/data`: 30T ext4 on NVMe RAID0, about 15T available.
- `/wea-fs/data`: NFS view of the same 30T data area.
- `/wea-fs/scratch`: NFS scratch on same large data pool.
- `/atd15/scratch`: 160T NFS, about 156T available.
- Several `/atdXX/scratch` mounts at 3.5T each.

Block devices:

- `/data` is `md124`, ~29.9T RAID0 across multiple 3.5T Micron 7450 NVMe drives.
- OS/home is on separate RAID1/LVM-backed NVMe devices.

Backend cache rule:

```text
/data/stormdeck/     = derived cache, manifests, indexes, quicklooks, render products
/atd15/scratch/...   = source/working ATD data, not necessarily StormDeck-owned
/home/atd_test/...   = user-space source checkout and small dev artifacts
/dev/shm             = temporary high-speed scratch only, never durable state
```

Important caveat:

- `/data` is RAID0: fast, large, and appropriate for cache/derived products, but not a safe sole authoritative archive unless externally backed up.

Recommended layout:

```text
/data/stormdeck/
  config/
  logs/
  source_index/
  cases/
    KATD_YYYYMMDD_HHMMSS/
      case_manifest.json
      source_refs.json
      provenance.json
      cfradial/
      metadata/
      quicklooks/
      render_cache/
        native_sweeps/
        decimated/
        fullres/
        masks/
      storm_objects/
      annotations/
      exports/
  tmp/
```

## 5. Network topology

Observed interfaces/routes:

```text
enp75s0f0  192.168.4.12/24   default route metric 101, 1 GbE
ens3f0np0  172.16.1.30/24    default route metric 102, 100 GbE
```

The high-speed NIC `ens3f0np0` reported:

```text
Speed: 100000Mb/s
Duplex: Full
Port: Direct Attach Copper
Link detected: yes
```

Backend serving implications:

- Prefer `172.16.1.30` / `ens3f0np0` for internal GPU renderer clients and large case/cache movement.
- Keep `192.168.4.12` / `enp75s0f0` as management/default/fallback path.
- Do not bind public-facing services to `0.0.0.0` by accident.
- MVP server can start localhost-only; internal lab mode can bind explicitly to `172.16.1.30`.

Suggested config:

```yaml
server:
  safe_default_host: "127.0.0.1"
  lab_data_host: "172.16.1.30"
  port: 8765
  allowed_clients: []   # fill with lab GPU workstation/VPN ranges after approval
```

Network conclusion:

- LVL2/CfRadial volumes around 10-12 MB are easy to move on 100 GbE.
- Still cache aggressively, because not every client will be on 100 GbE and scrubbing should be responsive.

## 6. Access and deployment constraints

Observed identity/permissions:

```text
uid=1006(atd_test)
gid=1000(par)
groups=1000(par)
passwordless sudo works
sbatch not found
qsub not found
```

Environment constraints stated by Bryan/Stephen:

- Government computer.
- Some control over installing software, but limited.
- Closed off from outside world.
- VPN required for remote connection.
- Compiled binaries are acceptable if Bryan/Stephen compiles them locally.

Deployment rules:

- No runtime cloud dependency.
- No external downloads during normal execution.
- Avoid externally supplied prebuilt binaries.
- Prefer source-delivered utilities, Makefiles, Python code, and locally built artifacts.
- Python dependencies should come from approved system packages or an offline wheelhouse.
- Podman exists; Docker, Singularity, Apptainer, and environment modules were not observed.
- No scheduler-first assumption; normal user-space services and later systemd are appropriate.

## 7. Installed backend toolchain

Observed tools/packages:

- Python 3.9.18 at `/usr/bin/python3`.
- pip 21.2.3.
- Podman available.
- `ncdump` available.
- `h5dump` 1.12.1 available.
- `nc-config` available.
- NetCDF C library 4.8.1.
- GCC/G++ 11.4.1.
- GNU Make 4.3.
- `fio` 3.35 available.
- `cmake` not found.
- Docker not found.
- Singularity/Apptainer not found.
- `module` not found.

Python package checks evolved during the discussion:

- Initial `chk-py.sh`: numpy/netCDF4/h5py/xarray/matplotlib/PIL unavailable in that Python environment.
- Later `chk-pyt.sh`: `numpy 1.23.5`, `netCDF4 1.5.8`, NetCDF lib `4.8.1` working.
- `python3-pillow` was installed successfully via `dnf` from EPEL.

MVP backend dependency baseline:

```text
Required now:
  python3
  numpy
  netCDF4
  ncdump
  cfile_to_cfradial
  cfile_dump
  Pillow or matplotlib for quicklooks, if approved/installed

Nice later:
  h5py
  xarray
  scipy
  pyproj
  zarr
  FastAPI/uvicorn
  orjson
```

## 8. Internal radar data layout

Observed ATD source pattern:

```text
/atd15/scratch/data/ATD/YYYY/MMDD/HHMMSS/
  LVL2/
    CFILE/
      KATD_Base_Data_YYYYMMDD_HHMMSS_fraction.cfl
    NEXRAD/
      KATDYYYYMMDDHHMMSS.0.raw
  LVL1/
    IQ/
      KATD_IQ_YYYYMMDD_HHMMSS_fraction.cfl
```

Example observed:

```text
/atd15/scratch/data/ATD/2026/0521/141544/LVL2/CFILE/
  KATD_Base_Data_20260521_141544_151077700.cfl
  KATD_Base_Data_20260521_141553_927013700.cfl
  KATD_Base_Data_20260521_141603_702949700.cfl
```

Case indexer grouping keys:

- Radar ID from filename and metadata: `KATD`.
- Date path: `YYYY/MMDD`.
- Case/scan directory: `HHMMSS`.
- Level: `LVL2` or `LVL1`.
- Format/product: `CFILE`, `NEXRAD`, `IQ`.
- Timestamp from filename.
- Start/end times from internal CFILE/CfRadial metadata.
- Volume number and sequence numbers from internal metadata.

## 9. CFILE facts from Bryan/Stephen

### File model

Bryan/Stephen corrected the model:

```text
One CFILE contains one volume; each message is one radial.
```

Refinement from actual dump/converter:

- First message can be product metadata (`radar_product_t`), not a radial.
- Subsequent messages are radial-like payloads.
- Parser must parse by message type, not assume message number = radial number.

### Data sizes

Bryan/Stephen stated:

```text
LVL1 CFILE: about 12 GB per 90-second volume for 90 degrees of data.
LVL2 CFILE: about 10 MB, and these are the files StormDeck will work with.
```

Observed LVL2 file sizes:

- `.cfl`: about 12 MB.
- converted `.nc`: about 11 MB.

Design decision:

- MVP uses Level 2 base/moment data.
- Level 1/IQ is out of MVP interactive path and reserved for research/reprocessing tools.

### CFILE utilities

Observed:

```text
/home/atd_test/bin/lnux_x86_64/cfile_dump
cfile_to_cfradial
```

`cfile_dump` purpose from Bryan/Stephen:

- C utility that dumps the data.
- Installed on `wea-fs`.
- Limited summarization ability.
- Can at least omit payload for Level 1/Pulse Groups.
- Cannot output other formats.
- No-payload option may not omit anything meaningful for Level 2.
- No-payload was added because Level 1 dumps took about 45 minutes and now dump in about 45 seconds.

`cfile_dump -h` relevant options:

```text
-b msg_no       beginning message number
-d              do not dump data, mainly useful for Pulse Groups / Level 1 speed
-D              dump data type info only and not data
-i header       internal header message
-i msgid_index  internal message index
-n msg_count    number of messages
-s              summary of messages
-x              error checking / do not dump
-y              short form message name header
```

Recommended usage:

```bash
cfile_dump -x file.cfl
cfile_dump -s file.cfl
cfile_dump -i header file.cfl
cfile_dump -i msgid_index file.cfl
cfile_dump -b0 -n1 file.cfl      # product metadata in observed file
cfile_dump -b1 -n1 file.cfl      # first radial-like message when needed
```

Do not parse large numeric field arrays from text dumps for MVP. Use converter + NetCDF reader.

## 10. CFILE -> CfRadial conversion path

Observed converter help:

```text
Usage: cfile_to_cfradial [options] <input_file_or_directory> <output_directory>
Description: Convert self-descriptive C data files (.cfl) into CFRadial data files (.nc).
Options:
  -h    help
  -v    verbose logging
```

Observed conversion:

```bash
cfile_to_cfradial KATD_Base_Data_20260521_141544_151077700.cfl .
```

Observed output:

```text
Converting file KATD_Base_Data_20260521_141544_151077700.cfl -> ./KATD_Base_Data_20260521_141544_151077700.nc
Opened input CFile ...
Wrote 103 radials for final sweep in file at elevation 0.50.
Closed the current input cfile.
```

Backend decision:

- MVP should **wrap/use** the existing converter rather than reverse-engineering CFILE payloads.
- Conversion output becomes the stable StormDeck numeric ingest source.
- CFILE metadata commands still feed provenance and validation.

## 11. Converted CfRadial structure observed

Observed converted file:

```text
KATD_Base_Data_20260521_141544_151077700.nc
netCDF-4
```

Top-level attributes:

```text
Conventions = "Cf/Radial"
version = "2.0"
title = "PAR Radar Data"
institution = "NSSL"
source = "Phased Array Radar"
instrument_name = "KATD"
site_name = "KATD"
scan_name = "ATD Demo TPRT 1 Cut"
time_coverage_start = "2026-05-21T14:15:44Z"
time_coverage_end = "2026-05-21T14:15:53Z"
```

Group/dimensions:

```text
group: sweep_0
  time = 103
  range = 1963
  prt = 3
```

Coordinates/metadata:

```text
time(time)
range(range)
  units = meters
  meters_to_center_of_first_gate = 0
  meters_between_gates = 224.8443
azimuth(time)
elevation(time)
prt(time)
prt_sequence(time, prt)
prt_type(time)
nyquist_velocity(time)
```

Observed float fields:

```text
REF  dBZ                 reflectivity
VEL  meters/second       radial velocity
V1D  meters/second       radial velocity variant / 1D velocity
SW   meters/second       spectrum width
ZDR  dB                  differential reflectivity
LDR  dB                  linear depolarization ratio
DR   dB                  depolarization ratio
PHI  degree              differential phase
RHO  unitless            correlation coefficient HV
RHX  unitless            correlation coefficient HX
NYQ  meters/second       gate Nyquist
```

Observed unsigned-byte flag/QC fields:

```text
THR, THV, THW, THA  threshold flags
OVV                 overlaid velocity flag
OVW                 overlaid width flag
CLTR, CLTV, CLTW    clutter flags
```

Backend implication:

- StormDeck schema must preserve all fields, not only `REF` and `VEL`.
- Unknown or less-standard fields such as `V1D`, `DR`, `RHX`, threshold/overlay/clutter flags should be retained with source names and flagged as internal/specialized until officially mapped.

## 12. Product metadata from CFILE header/product message

Observed `cfile_dump -b0 -n1` first message:

```text
Message No 1: ID 0, <radar_product_t>
name = Base_Data
type = Weather
instance_no = 6
data_collection_start_event_time = 1779372944.012912272
vol_no = 1
archive = False
commit_time = 1779372955.275267178
```

Backend should preserve:

- Product name/type.
- Instance number.
- Data collection start event time.
- Commit time.
- Volume number.
- Archive flag.
- Source path and converter command/output.

This supports auditability and scan-age display.

## 13. Radar/site/beam metadata from CFILE radial dump

From the sample radial dump, important metadata included:

- Radar ID: `KATD`.
- Site: `Norman`.
- Latitude: `35.236259460`.
- Longitude: `-97.463691711`.
- Height: `369.724395752 m`.
- Frequency: `3020 MHz`.
- Nominal beamwidth: `1.58°`.
- Scan name: `ATD Demo TPRT 1 Cut`.
- Scan type: `PPI`.
- Collection type: `Triple PRT`.
- IQ format: `FloatIQ`.
- Transmit elevation: about `0.500001490°`.
- Transmit azimuth: about `45.266044617°`.
- Relative transmit azimuth/elevation and boresight fields are present.
- Nyquist velocity: about `49.733978271 m/s`.
- Beginning range: `0.0`.
- Range resolution: `0.224844337 km` / `224.844337 m`.
- Primary observed gate count: `1963`.

Design rule:

- Do not infer gate count from unrelated acquisition counters like `range_ticks`; use actual field array lengths / NetCDF dimensions.
- Preserve per-ray geometry and timing before any gridding.

## 14. Canonical StormDeck backend data model

### SourceCase

```json
{
  "case_id": "KATD_20260521_141544",
  "radar_id": "KATD",
  "source_root": "/atd15/scratch/data/ATD/2026/0521/141544",
  "levels": ["LVL2", "LVL1"],
  "products": ["CFILE", "NEXRAD", "IQ"],
  "created_at": "2026-05-21T14:15:44Z",
  "authority": "NSSL/ATD internal data",
  "provenance_status": "internal_research"
}
```

### SourceVolume

```json
{
  "volume_id": "KATD_Base_Data_20260521_141544_151077700",
  "source_format": "CFILE_LVL2",
  "source_path": "/atd15/scratch/data/ATD/2026/0521/141544/LVL2/CFILE/KATD_Base_Data_20260521_141544_151077700.cfl",
  "converted_cfradial_path": "/data/stormdeck/cases/KATD_20260521_141544/cfradial/KATD_Base_Data_20260521_141544_151077700.nc",
  "netcdf_kind": "netCDF-4",
  "volume_number": 1,
  "start_time_utc": "2026-05-21T14:15:44Z",
  "end_time_utc": "2026-05-21T14:15:53Z",
  "scan_name": "ATD Demo TPRT 1 Cut",
  "scan_type": "PPI",
  "collection_type": "Triple PRT",
  "radial_count": 103,
  "sweeps": ["sweep_0"]
}
```

### RadarSweep

```json
{
  "sweep_id": "sweep_0",
  "sweep_fixed_angle_deg": 0.5,
  "time_count": 103,
  "range_count": 1963,
  "range_units": "meters",
  "range_first_gate_m": 0.0,
  "range_spacing_m": 224.8443,
  "coordinate_variables": ["time", "range", "azimuth", "elevation", "prt", "prt_sequence", "prt_type", "nyquist_velocity"],
  "fields": ["REF", "VEL", "V1D", "SW", "ZDR", "LDR", "DR", "PHI", "RHO", "RHX", "NYQ", "THR", "THV", "THW", "THA", "OVV", "OVW", "CLTR", "CLTV", "CLTW"]
}
```

### RadarField

```json
{
  "source_name": "REF",
  "canonical_name": "reflectivity",
  "units": "dBZ",
  "dtype": "float32",
  "shape": [103, 1963],
  "fill_value": -9999.0,
  "coordinates": "elevation azimuth range",
  "truth_status": "observed_base_radar_moment",
  "qc_status": "converter_preserved"
}
```

### RenderFrame

```json
{
  "frame_id": "KATD_20260521_141544_sweep0",
  "source_volume_id": "KATD_Base_Data_20260521_141544_151077700",
  "geometry_mode": "native_radial_sweep",
  "primary_fields": ["reflectivity", "radial_velocity", "spectrum_width"],
  "payloads": {
    "native_radial_reflectivity": "render_cache/native_sweeps/REF_f16.bin",
    "native_radial_velocity": "render_cache/native_sweeps/VEL_f16.bin",
    "azimuth": "render_cache/native_sweeps/azimuth_f32.bin",
    "elevation": "render_cache/native_sweeps/elevation_f32.bin",
    "range": "render_cache/native_sweeps/range_f32.bin",
    "observed_mask": "render_cache/masks/observed_mask_u8.bin"
  },
  "labels_required": ["source", "scan_time", "scan_age", "field", "units", "sweep_elevation", "geometry_mode", "qc"]
}
```

## 15. Backend services

### 15.1 Source scanner

Responsibilities:

- Walk configured ATD roots such as `/atd15/scratch/data/ATD`.
- Recognize `YYYY/MMDD/HHMMSS/LVL2/CFILE`, `LVL2/NEXRAD`, `LVL1/IQ`.
- Generate a case index without reading full payloads.
- Track file size, mtime, ownership, permissions, and source path.
- Detect converted `.nc` products.

Output:

```text
/data/stormdeck/source_index/source_files.sqlite
/data/stormdeck/source_index/cases.json
```

### 15.2 CFILE validation/provenance service

Responsibilities:

- Run `cfile_dump -x` for integrity checks.
- Run `cfile_dump -s` for message summary.
- Run `cfile_dump -b0 -n1` to capture product metadata.
- Optionally capture header and msgid index.
- Store text outputs in provenance files.

Output:

```text
metadata/cfile_summary.txt
metadata/cfile_product_message_0001.txt
metadata/cfile_header.txt
metadata/cfile_msgid_index.txt
provenance.json
```

### 15.3 Converter wrapper

Responsibilities:

- Call `cfile_to_cfradial input.cfl output_dir`.
- Capture stdout/stderr and exit code.
- Verify `.nc` exists.
- Run `ncdump -k` to confirm `netCDF-4`.
- Run a lightweight header probe.

Do not silently overwrite converted products unless `--force` is explicit.

### 15.4 CfRadial probe/manifest builder

Responsibilities:

- Open converted NetCDF with Python `netCDF4`.
- Enumerate groups such as `sweep_0`.
- Capture dimensions, coordinates, fields, units, fill values, min/max/valid counts, and global attributes.
- Emit `case_manifest.json`, `volume_manifest.json`, and `field_manifest.json`.

### 15.5 Quicklook generator

Responsibilities:

- Generate static PNG/WebP quicklooks for case selection and QA.
- First products: `REF`, `VEL`, `SW` PPI images.
- Include source/time/field/elevation labels burned in or adjacent in JSON.
- Use Pillow/matplotlib depending on available packages.

### 15.6 Render-cache builder

Responsibilities:

- Convert NetCDF arrays to GPU/client-friendly payloads.
- Start with native radial arrays and geometry buffers.
- Add decimated grids later.
- Preserve observed-sector mask and do not fabricate unobserved space.

Cache tiers:

```text
Tier 0: source CFILE / NEXRAD / IQ references
Tier 1: metadata manifests and SQLite index
Tier 2: quicklook images
Tier 3: decimated native sweep/render buffers
Tier 4: full-resolution native sweep/render buffers
Tier 5: semantic objects, annotations, tracks, warning/impact overlays
```

### 15.7 API/static server

MVP API should be simple:

- Static files for manifests and binary payloads.
- FastAPI for case list, volume list, frame metadata, export requests, and status.
- WebSocket only after replay is stable.
- gRPC only if binary streaming becomes painful.

Suggested endpoints:

```text
GET /health
GET /cases
GET /cases/{case_id}/manifest
GET /cases/{case_id}/volumes
GET /cases/{case_id}/frames
GET /cases/{case_id}/quicklooks/{field}/{frame}.png
GET /cases/{case_id}/payloads/{payload_path}
POST /jobs/convert
POST /jobs/build-cache
GET /jobs/{job_id}
```

## 16. Renderer-facing contract

Godot/WebGPU/other clients should not parse CFILE directly for MVP.

Renderer consumes:

- Case manifest.
- Frame manifest.
- Native radial field buffers.
- Geometry buffers: range, azimuth, elevation.
- Observed masks.
- Quicklooks.
- Storm objects / annotations / warning corridors.
- QC/provenance metadata.

Renderer must display persistently:

- Source file/product.
- Timestamp and scan age.
- Radar/site.
- Field name and units.
- Sweep/elevation.
- Observed vs interpolated/derived status.
- QC/provenance warnings.

## 17. Scientific visualization rules derived from the data

- Do not assume ATD/KATD covers 360 degrees.
- Do not assume NEXRAD VCPs or update cadences.
- Preserve sector coverage and scan geometry.
- Render native radial/PPI sectors before gridding into 3D Cartesian volumes.
- When gridding is introduced, generate and display an observed/interpolated mask.
- Do not render unobserved airspace as observed data.
- Keep Level 1/IQ separate from Level 2 base-data visualization.
- Preserve CFILE/CfRadial provenance because research PAR data can have calibration and steering-angle caveats.

## 18. MVP backend milestone plan

### Milestone A — source indexer

Input:

```text
/atd15/scratch/data/ATD/2026/0521/141544/LVL2/CFILE/*.cfl
```

Output:

```text
source_index.sqlite
case_manifest_stub.json
```

Done when:

- Case directories are discovered.
- CFILE/NEXRAD/IQ files are classified.
- LVL2 CFILE volumes are listed with sizes and timestamps.

### Milestone B — converter wrapper

Done when:

- One CFILE converts to NetCDF.
- stdout/stderr are captured.
- `.nc` kind is verified as `netCDF-4`.
- product message metadata is captured.

### Milestone C — CfRadial manifest probe

Done when:

- Python opens the `.nc` using `netCDF4`.
- Sweep dimensions and fields are listed.
- Field stats are computed for `REF`, `VEL`, `SW`.
- `volume_manifest.json` is emitted.

### Milestone D — quicklook QA

Done when:

- Reflectivity PPI quicklook renders from the converted file.
- Image includes field/time/elevation/source labels.
- Velocity quicklook handles diverging color scale and Nyquist metadata.

### Milestone E — native radial render cache

Done when:

- Field arrays and geometry arrays are exported to binary buffers.
- Frame manifest points to payload files.
- A renderer prototype can load and display a native radial sector or slice.

### Milestone F — API server

Done when:

- Internal client can retrieve cases, manifests, quicklooks, and payloads over `127.0.0.1` or `172.16.1.30` after approval.
- No cloud/runtime internet dependency.

## 19. Message accounting ledger

This section accounts for the Bryan/Stephen technical messages found in the available transcripts. Duplicate messages appeared across compacted/continued sessions; they are listed once conceptually with source IDs where useful.

1. Initial MWE guidance relayed by Jon: game-engine app, simulated reflectivity, hard-code early params, archived data later, live PAR last.
2. `id 442`: RHEL 9.1/Linux environment; app eventually runs on same server as shared data; asked whether Godot changes design.
3. `id 451`: Server graphics/CPU/RAM output; ASPEED AST2600, dual Xeon 4316, 80 CPUs, ~502 GiB RAM.
4. `id 512` / `id 637`: OS/kernel/filesystems/block devices/network basics; RHEL 9.1, large `/data`, ATD scratch NFS mounts, Python/fio/ip route context.
5. `id 514` + attachment: sample CFILE dump document.
6. `id 524`: Clarified sample was one radial in a volume file using custom CFILE dump.
7. `id 527`: User/group permissions and routing: `atd_test`, group `par`, passwordless sudo, no Slurm/PBS, `wea-fss`, routes via 192.168 and 172.16 networks.
8. `id 537`: One CFILE contains one volume; each message is one radial.
9. `id 539`: Level 1 CFILE about 12 GB per 90-second/90-degree volume; corresponding Level 2 CFILE about 10 MB; StormDeck works with Level 2.
10. `id 543`: Government/closed computer; limited install control; VPN required for remote connection.
11. `id 545`: `cfile_dump` is a C utility on `wea-fs`; can dump/summarize/omit payload in limited ways; cannot output other formats; converter to NetCDF exists; recorder to direct NetCDF is in progress.
12. `id 547` / `id 672`: Compiled binaries are fine if Bryan/Stephen compiles them locally.
13. `id 549` / `id 674`: Python/toolchain inventory: Python 3.9.18, pip, Podman, ncdump, h5dump, GCC/G++, Make; no module, Docker, Singularity, Apptainer, CMake.
14. `id 581` / `id 676`: `cfile_dump -h` options.
15. `id 583` / `id 678`: `cfile_dump` path; `cfile_to_cfradial` help; actual conversion of KATD CFILE to `.nc`; observed 103 radials at elevation 0.50; file listing and sizes.
16. `id 586` / `id 681`: `cfile_dump -b0 -n1` product metadata message showing `radar_product_t`, `Base_Data`, collection start, vol_no, commit_time.
17. `id 629` / `id 685`: No-payload option may not omit meaningful Level 2 payload; it mainly makes Level 1 dumps faster, from ~45 minutes to ~45 seconds.
18. `id 631` / `id 687`: Full `ncdump -h` of converted NetCDF; Cf/Radial 2.0, KATD, sweep_0, dimensions, coordinates, fields, QC flags.
19. `id 689`: `cfile_dump -s` summary showing message table with first product message and many radial messages around 117 KB each.
20. `id 694`: `ncdump -k` confirmed converted file is `netCDF-4`.
21. `id 696`: Python package check initially missing common science packages; Bryan/Stephen can install packages; more freedom on `wea-fs` than other machine.
22. `id 728`: DNF repo/package availability and install context; confirms RHEL/EPEL-style package path is available in this environment.
23. `id 738`: `nc-config --all`; NetCDF 4.8.1 built with NetCDF-4/HDF5/DAP support, no parallel NetCDF.
24. `id 740`: `ens3f0np0` is active 100 GbE.
25. `id 760`: `chk-pyt.sh` confirmed `numpy 1.23.5`, `netCDF4 1.5.8`, NetCDF lib 4.8.1.
26. `id 789`: `/data` write test succeeded; `python3-pillow` install via `dnf` succeeded.

## 20. Open backend questions for Bryan/Stephen

Only ask these when they unblock implementation:

1. Is `/data/stormdeck` an acceptable cache root for derived products?
2. Should the first internal case be `2026/0521/141544`, or is there a more meteorologically interesting case Bryan wants first?
3. Can a StormDeck service bind to `172.16.1.30:<port>` for a GPU workstation, or should access be SSH-tunnel-only initially?
4. Is `cfile_to_cfradial` stable enough to treat as the MVP numeric ingest path?
5. Will the direct NetCDF recorder produce the same CfRadial 2.0 structure as the converter output?
6. Are official definitions available for `V1D`, `DR`, `RHX`, `THR/THV/THW/THA`, `OVV/OVW`, `CLTR/CLTV/CLTW`?
7. Is `/data` backed up or strictly scratch/cache?
8. What GPU workstation will run the renderer, and can it reach `172.16.1.30`?

## 21. Bottom line

Bryan/Stephen's messages move StormDeck from a generic game-engine radar concept to a concrete NSSL/KATD backend architecture:

```text
wea-fs is the StormDeck data factory.
LVL2 CFILE is the first internal source format.
cfile_to_cfradial is the pragmatic MVP bridge.
Python netCDF4 is sufficient for the first manifest/cache builder.
/data/stormdeck should hold derived cache products.
100 GbE makes rich internal client/server workflows realistic.
The renderer still belongs on a separate real GPU workstation.
```

The central backend principle is now clear:

> Preserve KATD radial truth first; make it renderable second; make it pretty only after it cannot lie.
