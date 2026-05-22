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
- `tests/test_stormdeck_case_probe.py` — unit tests for geometry classification, range summaries, volume-type inference, and ATD missing-value masking.

Install dependencies on the target workstation:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Run the lightweight tests without radar data:

```bash
python -m pytest -q
```

Run the case probe against a local CfRadial file:

```bash
python scripts/stormdeck_case_probe.py /path/to/cfrad-file.nc --out stormdeck_case_probe_export
```

Build the smaller engine-facing volume index from the generated probe manifest:

```bash
python scripts/stormdeck_volume_index.py stormdeck_case_probe_export/<case-name>/manifest.json
```

Known better-quality `wea-fs` validation input:

```text
/home/atd_test/storm-deck-data/KATD_Base_Data_20260522_123630_436049100.nc
```

Local radar inputs and generated imagery are intentionally ignored by git under `data/`, `renders/`, and `stormdeck_case_probe_export/`.

## Revision v0.2

The spec now includes a step-by-step failure-mode section and gates for case selection, THREDDS download, CfRadial parsing, ATD sector coverage, geospatial validation, QC/artifacts, rendering, timeline deltas, semantic objects, UX, and exports.
