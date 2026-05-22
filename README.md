# StormDeck

StormDeck is a game-engine-powered 4D severe-weather interface concept for phased-array radar, NEXRAD, and radar-derived storm data.

## Posted specs

- [Rolling interactive spec deck](docs/rolling-spec.html) — current source of truth for bottleneck, next action, milestones, schemas, and iteration log.
- [Bryan inputs recall log](docs/bryan-inputs.md) — durable Markdown log for Bryan-provided requirements, constraints, hardware details, and future updates.
- [Interactive ATD initial spec](stormdeck-atd-initial-spec.html)
- [Failure-mode review](docs/failure-modes.md)

The rolling spec currently prioritizes a synthetic game-engine MWE before archived radar ingest. Bryan-provided information should be recorded in `docs/bryan-inputs.md` for reliable recall. The ATD artifact focuses on NOAA/NSSL Advanced Technology Demonstrator data output, especially public `KATD` CfRadial 1 NetCDF files from the NSSL THREDDS archive.

## MVP framing

StormDeck v0 starts with archived replay data, not live PAR access. It should load a public ATD case, preserve true sector geometry, render time-scrubbable reflectivity and velocity, support slicing, show storm motion and scan age, include at least one semantic storm object, and expose a “what changed in the last 60 seconds” panel.

## Prototype code

The repository now includes a small Python prototype layer for archived ATD/KATD CfRadial files:

- `scripts/stormdeck_single_frame_preview.py` — first-pass single-frame preview renderer.
- `scripts/stormdeck_3d_frame_render.py` — observed-gate 3D frame renderer for an actual radar sweep.
- `scripts/stormdeck_case_probe.py` — grouped CfRadial case probe that classifies PPI sector/RHI geometry, summarizes fields, writes a manifest, and optionally exports quicklook PNGs.
- `scripts/stormdeck_field_preview.py` — browser-safe `stormdeck.field_preview.v0` exporter for one observed native sweep field sample.
- `tests/test_stormdeck_case_probe.py` — unit tests for geometry classification, range summaries, volume-type inference, and ATD missing-value masking.

Install dependencies on the target workstation:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

Run the lightweight tests without radar data:

```bash
python3 -m pytest -q
```

Run the case probe against a local CfRadial file:

```bash
python3 scripts/stormdeck_case_probe.py /path/to/cfrad-file.nc --out stormdeck_case_probe_export
```

Build the smaller engine-facing volume index from the generated probe manifest:

```bash
python3 scripts/stormdeck_volume_index.py stormdeck_case_probe_export/<case-name>/manifest.json
```

Build a case-level timeline from a metadata inventory JSON:

```bash
python3 scripts/stormdeck_case_timeline.py \
  --inventory /path/to/mvol-su.txt \
  --case-id 20260402_031550_supercell \
  --out /data/stormdeck/exports/20260402_031550/case_timeline.json
```

Build comparable temporal tracks for replay and future “what changed” panels:

```bash
python3 scripts/stormdeck_temporal_tracks.py \
  --inventory /path/to/217-volumes.txt \
  --case-id 20260402_031550_supercell \
  --out /data/stormdeck/exports/20260402_031550/temporal_tracks.json
```

The temporal-tracks exporter classifies complete scan products separately from transition fragments, quarantines tiny or partial products by default, and only groups comparable observations into the same track. For the validated KATD supercell inventory, the expected operational lanes are low-level sector scans, complete 20-sweep Supercell 3D volumes, complete 9-sweep native RHI volumes, and a quarantine/debug lane for fragments.

Build a metadata-safe “what changed” summary from temporal tracks:

```bash
python3 scripts/stormdeck_change_summary.py \
  --temporal-tracks /data/stormdeck/exports/20260402_031550/temporal_tracks.json \
  --out /data/stormdeck/exports/20260402_031550/change_summary.json
```

The change-summary exporter does not read radar arrays or compute reflectivity/velocity deltas. It reports same-track comparison windows, elapsed time, cadence status, and nearby quarantine events so the replay UI can show an honest first “what changed” panel.

Export one observed radar field sample for the cockpit. This reads one CfRadial sweep, masks missing gates, downsamples the native ray/gate array for browser use, and does not grid or interpolate:

```bash
python3 scripts/stormdeck_field_preview.py \
  /path/to/complete-volume.nc \
  --field REF \
  --sweep-index 0 \
  --out /data/stormdeck/exports/20260402_031550/field_preview.json
```

Open the metadata replay cockpit scaffold:

```bash
python3 -m http.server 8765
```

Then open:

```text
http://localhost:8765/viewer/index.html
```

Load `case_timeline.json`, `temporal_tracks.json`, and `change_summary.json` with the file pickers. Optionally load `field_preview.json` to draw a sampled native polar sweep of observed gates. When the CfRadial file includes radar site latitude and longitude, the viewer also draws a radar site marker and sector outline for geographic context. Optionally load `map_overlays.json` (`stormdeck.map_overlays.v0`) to add towns, state/county boundary linework, and warning corridor polygons as context overlays on the orientation sketch only. That context is deliberately not a gridded or map-projected gate field. The viewer intentionally displays observed metadata, pairing rules, scan age, provenance, confidence, uncertainty, warnings, temporal tracks, and the quarantine/debug lane; the optional field preview is not a gridded volume, not 3D, and not a radar field delta.

Minimal `map_overlays.json` shape:

```json
{
  "schema": "stormdeck.map_overlays.v0",
  "town_points": [
    { "name": "Norman", "latitude_deg": 35.2226, "longitude_deg": -97.4395 }
  ],
  "warning_corridors": [
    {
      "id": "demo-warning-corridor",
      "points": [
        { "latitude_deg": 35.0, "longitude_deg": -98.0 },
        { "latitude_deg": 35.3, "longitude_deg": -98.0 },
        { "latitude_deg": 35.3, "longitude_deg": -97.5 },
        { "latitude_deg": 35.0, "longitude_deg": -97.5 }
      ]
    }
  ],
  "county_boundaries": [],
  "state_boundaries": []
}
```

Or scan a CfRadial directory directly on `wea-fs`:

```bash
python3 scripts/stormdeck_case_timeline.py \
  --glob '/home/atd_test/storm-deck-data/20260402_031550/CFILE/cfradial/*.nc' \
  --case-id 20260402_031550_supercell \
  --out /data/stormdeck/exports/20260402_031550/case_timeline.json
```

Summarize the generated timeline by pointing `p` at the absolute output path:

```bash
python3 - <<'PY'
import json
p = "/data/stormdeck/exports/20260402_031550/case_timeline.json"
m = json.load(open(p))
print("schema:", m["schema"])
print("case_id:", m["case_id"])
print("volume_count:", m["volume_count"])
print("case_start_time:", m["case_start_time"])
print("case_end_time:", m["case_end_time"])
print("median_volume_start_spacing_s:", m["median_volume_start_spacing_s"])
print("scan_name_counts:", m["scan_name_counts"])
print("scan_mode_counts:", m["scan_mode_counts"])
print("playlist_pattern_sample:", m["playlist_pattern_sample"])
print("warnings:")
for w in m["warnings"]:
    print("-", w)
print("scan_summaries:")
for name, s in m["scan_summaries"].items():
    print(name, s)
PY
```

Known `wea-fs` validation input:

```text
/home/atd_test/storm-deck-data/KATD_Base_Data_20260522_123630_436049100.nc
```

Data provenance note: this validation file is simulator-produced data based on real weather data, not a fully public real-data release. Treat simulator artifacts and impurities as possible. Do not commit radar input files, generated quicklooks, or exported manifests unless they have been explicitly approved for public consumption.

Local radar inputs and generated imagery are intentionally ignored by git under `data/`, `renders/`, and `stormdeck_case_probe_export/`.

## Revision v0.2

The spec now includes a step-by-step failure-mode section and gates for case selection, THREDDS download, CfRadial parsing, ATD sector coverage, geospatial validation, QC/artifacts, rendering, timeline deltas, semantic objects, UX, and exports.
