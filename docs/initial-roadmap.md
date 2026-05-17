# StormDeck Initial Roadmap

## Product vision

StormDeck is a real-time 4D storm cockpit that converts radar volumes and radar-derived objects into an interactive, geospatially aligned severe-weather workspace. It helps expert users see what changed, what matters, who is affected, and what action is warranted faster than conventional frame-by-frame radar workflows.

## MVP assumptions

- Use archived public radar data first.
- Do not require live PAR access.
- Build replay mode before live mode.
- Run on one high-end workstation.
- Use manual or simple semantic annotation before attempting full AI detection.
- Use the NOAA/NSSL Advanced Technology Demonstrator (ATD / `KATD`) as the first concrete PAR target where public data are available.
- Start ATD ingest with public CfRadial 1 NetCDF data from the NSSL THREDDS archive; keep NEXRAD MSG31/raw and raw I/Q paths as later options.
- Treat ATD as single-face sector PAR data; do not imply 360° coverage.
- See `docs/atd-data-references.md` for ATD documentation, URLs, verified sample fields, and parser implications.

## MVP target capabilities

- Load one archived severe-weather radar case.
- Convert radar data into a geospatially aligned 3D/4D scene.
- Render time-scrubbable reflectivity and velocity layers.
- Support horizontal/vertical slicing.
- Show storm motion and scan age.
- Add one selectable semantic storm object.
- Display a “what changed in the last 60 seconds” panel.
- Overlay map/terrain/towns/warning corridor.
- Export screenshots/video for demo.

## Recommended starting stack to evaluate

- Backend/data exploration: Python, Py-ART, xarray, numpy, scipy, netCDF/HDF5/Zarr as needed.
- Geospatial: pyproj, rasterio/geopandas as needed; Cesium/Mapbox/deck.gl if web-native.
- Renderer candidates:
  - Unity for fastest practical 3D prototype.
  - Unreal for high-end cinematic/VR command-center demo.
  - WebGPU/Three.js/deck.gl for browser-first collaboration.
- Streaming later: WebSocket/gRPC/NATS; start offline/replay first.

## First 2-week feasibility plan

### Week 1: data and volume spike

1. Select one archived severe-weather radar case, preferably a public ATD/KATD CfRadial case from the NSSL THREDDS archive.
2. Load radar data and inspect available fields.
3. Convert one or more sweeps/volumes into a Cartesian representation while preserving the true ATD sector footprint.
4. Export a compact render-friendly format.
5. Validate geospatial alignment against map coordinates.

### Week 2: renderer and UX spike

1. Render reflectivity volume or stacked slices in the chosen engine.
2. Add timeline scrubber.
3. Add map/terrain/town overlay.
4. Add vertical/horizontal slicing.
5. Add one manually annotated storm object.
6. Add “what changed” panel using simple deltas/manual notes.
7. Export a demo screenshot/video.

## Dream architecture

Radar/PAR feed → edge preprocessing/QC → central storm-state backend → object/trend extraction → game-engine clients → forecaster/emergency/training modes.

## Hardware questions to answer early

Radar side:
- What data level is available: raw I/Q, moments, gridded volumes, derived objects?
- For ATD v0, verify exact CfRadial fields per case: reflectivity, velocity, spectrum width, ZDR, differential phase/PHIDP, RHOHV, and KDP where present.
- What is the update cadence?
- What latency is acceptable?
- What should be archived for replay/training?
- What sector/beam coverage exists, and how should missing unsampled space be visualized?

Render side:
- What grid/volume resolution is useful?
- How many fields and time steps must be resident on GPU?
- What FPS target is realistic for desktop vs VR vs video wall?
- What GPU tier is required for a credible demo?

## Early risks

- Pretty 3D may mislead or overload forecasters.
- Coordinate transforms/geospatial alignment can quietly break trust.
- Live PAR access may be unavailable; archived replay must carry v0.
- The exact 2026 Caney ATD case may not be publicly available yet; use public 2023 ATD cases first and keep Caney as an access/request target.
- ATD is single-face sector PAR data; rendering unsampled space as if it were observed would destroy trust.
- ATD data are minimally quality controlled research data; ZDR bias, range folding, velocity aliasing, clutter, and sidelobe artifacts must be surfaced, not hidden.
- GPU memory can become the limiting factor.
- Raw radar products may require specialized QC/dealiasing before visualization.
- Operational users may reject any UI that slows warning decisions.
