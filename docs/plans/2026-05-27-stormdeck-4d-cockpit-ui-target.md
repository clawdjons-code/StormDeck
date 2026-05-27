# StormDeck 4D Cockpit UI Target Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Define the concrete UI destination and first feature contract for the StormDeck 4D replay cockpit so implementation is deliberate, not random accretion.

**Architecture:** Keep the current PPI/bundle viewers as inspectors. Build a new 4D mainline around an engine-readable scene manifest and a dedicated cockpit page that visualizes time, stacked sweep slabs, semantic objects, readiness, and caveats. The first implementation remains browser/static and screenshot-friendly; Godot/WebGPU can consume the same manifest later.

**Tech Stack:** Python 3 scripts for manifest generation, JSON schema-style contracts, pytest for TDD, static HTML/CSS/JS for the cockpit prototype, local HTTP server for validation.

---

## Product target: StormDeck 4D Replay Cockpit v0.1

The UI we are working toward is an **operational 4D replay cockpit**, not a prettier PPI browser.

The center of the screen should answer, at a glance:

1. **What time/frame am I viewing?**
2. **What 3D/4D storm structure is being approximated?**
3. **Which radar sweeps/fields make up the current scene?**
4. **What changed recently, and is that comparison valid?**
5. **Which semantic storm objects are selected, and are they observed, derived, or manual?**
6. **What caveats prevent over-interpretation?**

## Target layout

### Header: provenance and clock

- Product label: `StormDeck 4D Replay Cockpit`
- Case ID
- Radar/source
- Replay time
- Scan age
- Data mode badge: `observed native sweeps`, `sample quicklooks`, or future `gridded volume`
- Global caveat badge: `not live`, `not adaptive tasking`, `not true gridded 3D` when applicable

### Left rail: 4D timeline and frame stack

- Timeline scrubber keyed by volume/frame time
- Frame list grouped by `volume_id`
- Per-frame badges:
  - field: REF / VEL / SW
  - sweep name/index
  - elevation/fixed angle
  - quicklook/texture availability
  - comparable vs browse-only
- Playback controls are okay, but must say `frame browsing`, not storm-motion interpolation unless compatibility proves otherwise.

### Center viewport: 4D scene stage

Initial v0.1 scene representation:

- Stacked sweep/slab cards or pseudo-3D layers using existing quicklook PNG textures.
- Layers separated by elevation/fixed angle.
- REF/VEL/SW can be toggled as scene layers, but only one can be dominant by default.
- The viewport must label:
  - `Observed quicklook texture`
  - `Stacked sweep visualization`
  - `Not a gridded 3D retrieval`
  - `Not interpolated between unobserved gates`
- Screenshot mode should prioritize this center viewport and enlarge text, because review screenshots may be cropped/zoomed.

### Right rail: storm objects, what-changed, readiness

- Semantic object panel:
  - object ID/name
  - type: manual/sample/derived/observed
  - confidence
  - linked frames or volumes
  - interpretation limit
- What-changed panel:
  - starts metadata-only if no comparable value deltas exist
  - reports elapsed time, scan age, added/missing frames, changed sweep availability
  - refuses invalid comparison with explicit language
- Readiness panel:
  - required artifacts present/missing
  - texture/quicklook counts
  - semantic object status
  - comparison compatibility status

## First concrete feature set

### Feature 1: 4D scene manifest exporter

Create `scripts/stormdeck_4d_scene_manifest.py`.

Input:

- A replay bundle root containing `stormdeck_bundle_manifest.json` or source files accepted by `stormdeck_build_bundle_manifest.py`.
- Optional `semantic_objects.json`.

Output:

- `stormdeck_4d_scene_manifest.json`

Schema:

```json
{
  "schema": "stormdeck.4d_scene_manifest.v0",
  "case_id": "...",
  "scene_mode": "stacked_native_sweep_quicklooks",
  "data_truth_level": "observed_native_quicklook_textures",
  "gridded_3d": false,
  "interpolated": false,
  "timeline": [
    {
      "time_index": 0,
      "volume_id": "...",
      "start_time": "...",
      "end_time": "...",
      "scan_age_label": "replay-relative",
      "layers": [
        {
          "layer_id": "...",
          "field": "REF",
          "sweep_name": "sweep_0",
          "fixed_angle_deg": 0.5,
          "texture_path": "volumes/.../quicklooks/sweep_0_REF.png",
          "texture_exists": true,
          "provenance": "observed_native_quicklook_png",
          "interpretation_limit": "stacked_sweep_not_gridded_3d"
        }
      ],
      "comparison_status": "browse_only_not_comparable"
    }
  ],
  "semantic_objects": [],
  "readiness": {
    "status": "ready|degraded|missing_inputs",
    "timeline_frame_count": 1,
    "texture_count": 3,
    "missing_texture_count": 0,
    "semantic_object_count": 0
  },
  "warnings": [
    "Stacked native sweep quicklooks are not a gridded 3D retrieval.",
    "Frame playback is browsing unless compatibility marks comparison safe."
  ]
}
```

Acceptance criteria:

- Groups bundle frames by volume/time into timeline entries.
- Converts quicklook paths into scene layer `texture_path` values.
- Preserves `field`, `sweep_name`, `fixed_angle_deg`, `volume_id`, and provenance.
- Emits explicit honesty flags: `gridded_3d: false`, `interpolated: false`.
- Loads semantic objects if present; otherwise emits an empty list and a readiness note.
- Provides clear readiness counts.

### Feature 2: 4D cockpit static viewer

Create `viewer/4d_cockpit.html`.

Required UI sections:

- `id="scene-header"`
- `id="scene-readiness"`
- `id="scene-timeline"`
- `id="scene-stage"`
- `id="scene-layer-stack"`
- `id="semantic-objects"`
- `id="what-changed"`
- `id="scene-caveats"`

Required controls:

- Local file loader for `stormdeck_4d_scene_manifest.json`.
- Timeline frame selection.
- Field/layer visibility toggle.
- Screenshot mode toggle with large center viewport typography.

Required language in UI/tests:

- `StormDeck 4D Replay Cockpit`
- `stacked native sweep quicklooks`
- `not a gridded 3D retrieval`
- `not interpolated between unobserved gates`
- `frame browsing, not storm-motion interpolation`
- `semantic objects may be manual/sample unless marked otherwise`

### Feature 3: README run path

Add a concise 4D workflow to `README.md`:

```bash
python3 scripts/stormdeck_build_bundle_manifest.py /path/to/KATD_sample_inventory
python3 scripts/stormdeck_4d_scene_manifest.py /path/to/KATD_sample_inventory
python3 -m http.server 8765
```

Open:

```text
http://localhost:8765/viewer/4d_cockpit.html
```

Load:

```text
/path/to/KATD_sample_inventory/stormdeck_4d_scene_manifest.json
```

### Feature 4: tests

Add tests before implementation:

- `tests/test_stormdeck_4d_scene_manifest.py`
  - exporter emits `stormdeck.4d_scene_manifest.v0`
  - groups layer frames into timeline entries
  - preserves texture paths and fixed-angle/elevation metadata
  - counts missing textures
  - loads semantic objects if present
  - emits non-gridded/non-interpolated caveats

- `tests/test_4d_cockpit_viewer.py`
  - required UI IDs exist
  - file loader exists
  - cockpit honesty language exists
  - screenshot mode exists
  - renderer function names exist, e.g. `renderSceneManifest`, `renderSceneTimeline`, `renderSceneStage`, `renderSemanticObjects`, `renderWhatChanged`

## TDD execution tasks

### Task 1: exporter tests RED

**Objective:** Add tests for the 4D scene manifest contract before writing the exporter.

**Files:**

- Create: `tests/test_stormdeck_4d_scene_manifest.py`

**Verification:**

```bash
pytest tests/test_stormdeck_4d_scene_manifest.py -q
```

Expected: FAIL because `scripts/stormdeck_4d_scene_manifest.py` does not exist yet.

### Task 2: exporter GREEN

**Objective:** Implement the minimal exporter that passes the scene manifest tests.

**Files:**

- Create: `scripts/stormdeck_4d_scene_manifest.py`

**Verification:**

```bash
pytest tests/test_stormdeck_4d_scene_manifest.py -q
pytest tests/test_stormdeck_build_bundle_manifest.py -q
```

Expected: PASS.

### Task 3: viewer tests RED

**Objective:** Add scaffold tests for the dedicated 4D cockpit page.

**Files:**

- Create: `tests/test_4d_cockpit_viewer.py`

**Verification:**

```bash
pytest tests/test_4d_cockpit_viewer.py -q
```

Expected: FAIL because `viewer/4d_cockpit.html` does not exist yet.

### Task 4: viewer GREEN

**Objective:** Implement the minimal 4D cockpit static page.

**Files:**

- Create: `viewer/4d_cockpit.html`

**Verification:**

```bash
pytest tests/test_4d_cockpit_viewer.py -q
```

Expected: PASS.

### Task 5: README workflow

**Objective:** Document exactly what Jon/Bryan should run next.

**Files:**

- Modify: `README.md`

**Verification:**

```bash
pytest tests/ -q
```

Expected: all tests pass.

### Task 6: browser smoke

**Objective:** Prove the viewer loads locally before asking the user to run it.

**Commands:**

```bash
python3 -m http.server 8765
# open http://127.0.0.1:8765/viewer/4d_cockpit.html
```

Check:

- Page loads.
- No JavaScript errors.
- File loader is visible.
- Screenshot mode toggles.

## Non-goals for this batch

- No Godot project yet.
- No WebGPU dependency yet.
- No true gridded volumetric retrieval.
- No AI/algorithmic tornado detection.
- No live radar ingest.
- No hidden smoothing/interpolation.

## Decision gates

### Gate 1: UI target approval

Before implementation, confirm this is the UI target: **4D Replay Cockpit v0.1** with center-stage stacked native sweep quicklooks and explicit caveats.

### Gate 2: exporter contract approval

Do not add additional scene schema fields unless needed for the UI sections above.

### Gate 3: ready-to-run handoff

Only tell the user to run the software after:

- tests pass,
- browser smoke passes,
- changes are committed/pushed,
- command block is exact.
