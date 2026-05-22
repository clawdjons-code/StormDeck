# StormDeck Conversation Digest — 2026-05-21

Last updated: 2026-05-21 18:10:42 CDT

Purpose: organize the current StormDeck / PARtalk conversation into a Markdown file that is easy for PARtner or another agent to parse before revising the HTML spec. This is not the public-facing spec; it is a working memory/index document.

## 1. Executive summary

- StormDeck has a GitHub repo and published Pages artifact:
  - Repo: `https://github.com/clawdjons-code/StormDeck`
  - Current published spec deck: `https://clawdjons-code.github.io/StormDeck/docs/rolling-spec.html`
  - Local workspace: `/Users/jonsclawdvandamn/Partner/StormDeck`
- The current HTML spec is a slide/deck-style single-file artifact centered on a clickable system architecture map.
- Jon does **not** like the current HTML formatting and wants to discuss the best format before more HTML work.
- Bryan’s core direct technical input is MWE-first:
  - Start with a game-engine app rendering **simulated reflectivity**.
  - Hard-code early parameters as needed.
  - Then feed archived data.
  - Then wire live operational PAR data.
- The latest group discussion challenged whether synthetic data should come before real data. The answer was nuanced:
  - Synthetic first is the shortest path to proving the renderer contract.
  - Real data first is valid if the first target is an honest **observed KATD PPI sector render**, not a polished fake 3D storm cube.
  - Best Bryan-facing/demo path: do both — synthetic 3D for capability, real KATD sector render for trust.

## 2. Source files currently involved

- `docs/rolling-spec.html`
  - Current interactive HTML spec deck.
  - Main visual focus: clickable architecture map.
  - Current status: formatted in a dense slide-deck style that Jon dislikes.
- `docs/bryan-inputs.md`
  - Durable recall log for Bryan-provided input.
  - Currently records one direct Bryan quote plus derived architecture decisions.
- `README.md`
  - Links to rolling spec and Bryan inputs log.
- `index.html`
  - Redirects to / points at the spec for GitHub Pages.
- `docs/atd-data-references.md`
  - Technical ATD/KATD data reference, including public sample CfRadial URL and verified metadata.
- `docs/initial-roadmap.md`
  - Older roadmap/spec framing for ATD/KATD, replay-first radar ingest, and failure gates.

## 3. Direct Bryan input captured so far

Source: `docs/bryan-inputs.md`; originally relayed by Jon in the PARtalk Telegram thread.

> Great! Howdy Bart- I mean PARtner.
>
> I’m interested in getting an MWE (minimum working example) going where we can see an app that uses a game engine to render a 3D display of simulated reflectivity data (hard-coding as many parameters as necessary). Then we can worry about feeding the engine more realistic archived data. After that, we can worry about wiring up a live stream of actual weather data from an operational PAR.

Parsed requirements:

- First deliverable: MWE / minimum working example.
- App type: game-engine app, not only a notebook/static image.
- First field/product: simulated reflectivity.
- Early simplification allowed: hard-code parameters.
- Build order:
  1. Synthetic simulated reflectivity MWE.
  2. Archived realistic radar data.
  3. Live operational PAR stream.

## 4. PARtalk group transcript fragments available in Hermes session DB

### 4.1 Group setup / permissions

- Jon: `Testing permissions`
- PARtner: `Permissions test received in Telegram group **PARtalk**. I can reply here.`
- Jon: `Ok Bryan is here.`

Operational note: Telegram group privacy and Hermes group authorization were later adjusted so Bryan/group messages can be seen without requiring `@` mention.

### 4.2 Request to Bryan: what data is needed from him

Jon asked: `Give Brian a concise summary of any other data you might need from him`

PARtner replied with requested Bryan follow-ups:

1. Target first radar case:
   - archived storm/event, radar site, date/time window, phenomena.
2. Operational workflow priority:
   - forecaster warning, radar research, emergency manager impact, or training/replay.
3. Minimum must-see products:
   - reflectivity, velocity, spectrum width, rotation/az shear, hail, debris signature, storm tracks, warning polygons.
4. Semantic storm-object definition:
   - mesocyclone, hail core, tornado warning area, storm cell, rotation couplet, manually annotated feature, etc.
5. Acceptable simplifications:
   - whether synthetic data/manually annotated objects are acceptable before real ingest.
   - what visualizations would be misleading/off-limits.
6. Hardware/runtime expectations:
   - target demo machine specs, resolution, FPS.
7. PAR future path:
   - raw I/Q, moments, gridded volumes, or derived object products.

Short form from that reply:

- Need Bryan’s preferred first weather case.
- Need first user workflow.
- Need must-have radar products.
- Need scientifically acceptable simplifications for prototype.

### 4.3 Sample-data question

User/group asked: `Do we have sample data to create a render from?`

Answer distilled:

- No sample radar/render-ready data is currently checked into the StormDeck repo.
- No local `.nc`, `.npy`, `.json`, `.cfl`, or `.ar2v` render-ready files were found under `/Users/jonsclawdvandamn/Partner/StormDeck` or `/Users/jonsclawdvandamn/Partner`.
- Yes, the repo docs identify a verified public ATD/KATD CfRadial sample source:

```text
https://data.nssl.noaa.gov/thredds/fileServer/RRDD/ATD/2023/0428/cfrad1/cfrad.20230428_162022.548_to_20230428_162041.283_KATD_PPI.nc
```

Verified sample properties from `docs/atd-data-references.md`:

- Radar/instrument: `KATD` / NSSL ATD.
- Format: CfRadial 1 NetCDF.
- Dimensions:
  - `time`: 206 rays.
  - `range`: 1964 gates.
  - `sweep`: 2.
- Fields observed:
  - `reflectivity` in dBZ.
  - `velocity` in meters_per_second.
  - `spectrum_width` in meters_per_second.
  - `differential_reflectivity` in dB.
  - `differential_phase` in degrees.
  - `cross_correlation_ratio` in ratio.
- Geometry:
  - latitude: 35.236259.
  - longitude: -97.463692.
  - altitude: 369 m.
  - azimuth coverage: about 270.3° to 359.7°.
  - elevation coverage: about 0.5° to 0.9°.
  - range spacing: 225 m.
  - max range: about 442 km.

Security/procedure note:

- NOAA sample file has not been downloaded because Jon’s security protocol says no external downloads without explicit approval.

### 4.4 Follow-up: “Ok so do we have data to create a render with?”

Answer distilled:

- Not locally.
- We have:
  - no local render-ready data files;
  - no downloaded `.nc`, `.npy`, `.raw`, or texture volume;
  - a verified public NOAA/NSSL KATD sample URL usable after approval;
  - enough schema/design info to generate synthetic sample data immediately without external download.

Recommended fast path from that answer:

1. Synthetic render today:
   - generate fake 3D reflectivity/velocity volume;
   - prove renderer loading, slicing, color maps, timeline;
   - no external download required.
2. Real radar render next:
   - download public KATD `.nc` after approval;
   - convert reflectivity/velocity to render-ready assets;
   - validate geometry and coverage honestly.

### 4.5 Follow-up: “Why not start with real data?”

Answer distilled:

- We can start with real data, but it couples two problems immediately:
  1. Can the engine render/interact with a radar-like 4D volume?
  2. Can the pipeline ingest real radar files without lying?
- Synthetic data isolates problem 1.
- Real data forces both problems at once.

Why synthetic first is safer:

- Cleaner renderer contract:
  - known `256×256×64`, units, origin, color range, cadence.
  - visual bugs are renderer/shader problems, not parser ambiguity.
- Real ATD data is radial/sector data, not a neat cube:
  - rays, gates, azimuths, elevations, sweeps.
  - approximately 90° sector, not 360°.
  - 3D display requires native radial/sweep rendering or Cartesian interpolation/gridding.
- Avoid misleading 3D:
  - never render unobserved space as if observed.
- Debugging is faster:
  - validate volume loading, timeline, color map, transparency, slicing, change panel, frame cache schema first.
- The verified KATD file is low-elevation PPI / 2D-to-2.5D, not a dramatic volumetric storm tower.

Honest real-data-first target:

- `Render observed KATD PPI sector slices accurately`
- Not: `Render a polished 3D storm volume`

Recommended sequence after this discussion:

1. Synthetic 3D cube for renderer plumbing.
2. Real KATD PPI sector render for scientific grounding.
3. Gridded 3D real radar volume only after geometry/coverage validation.

Best demo framing:

- Synthetic 3D for capability.
- Real KATD sector render for trust.

## 5. Current HTML spec formatting problem

Jon says: `I don't like how the spec HTML is formatted.`

Current likely pain points based on inspecting `docs/rolling-spec.html`:

- It is a slide deck, not a readable spec page.
- It hides much of the content behind navigation / one-slide-at-a-time interaction.
- The first-slide architecture map is visually dense and app-like.
- The layout is optimized for presentation theater, not for fast scanning, critique, or agent patching.
- The dark theme is high-contrast but may feel too styled/cinematic for an operational spec.
- Important engineering decisions are scattered across slides instead of forming a linear build document.
- The clickable map encodes system structure, but it may dominate the artifact before the actual implementation plan is clear.

## 6. Better HTML spec formatting options to discuss

### Option A — Linear operating spec with sticky architecture rail

Best default recommendation.

Shape:

- Single scrollable page.
- Left/main column: readable sections in priority order.
- Right/sticky rail: compact architecture map + current gate + next action.
- Details are visible by default or in simple `<details>` blocks.

Why it fits StormDeck:

- Easier for humans to scan.
- Easier for agents to patch with stable section IDs.
- Keeps architecture visible without making the whole spec a slide show.
- Works well on GitHub Pages and as a printable/PDF artifact.

Suggested section order:

1. Header: project, status, last updated, current gate.
2. One-screen decision summary.
3. Current next action and bottleneck.
4. Architecture map / pipeline.
5. MWE acceptance criteria.
6. Data path: synthetic → archived KATD → live PAR.
7. Renderer contract schemas.
8. Radar honesty / visualization rules.
9. Implementation plan.
10. Risks and gates.
11. Bryan input / stakeholder notes.
12. Iteration log.

### Option B — System architecture dossier

Shape:

- Not a slide deck.
- Architecture diagram at top.
- Each architecture node becomes a full anchored section below.
- Cross-links from diagram to node sections.

Why it fits:

- Very parseable.
- Keeps node model but makes details richer.
- Good if Bryan/Jon want to reason component-by-component.

Downside:

- Less visual punch than deck.
- More like engineering documentation.

### Option C — Two artifacts

Shape:

- `docs/rolling-spec.html`: operational living spec, mostly linear and readable.
- `docs/spec-deck.html`: presentation/deck version for demos.

Why it fits:

- Separates “work the project” from “show the project.”
- Avoids forcing one HTML file to be both dashboard and pitch deck.

Downside:

- More files to maintain.
- Need clear source-of-truth rule.

Recommended rule if using two artifacts:

- Markdown + linear HTML spec are source of truth.
- Deck is a generated/presentation derivative.

## 7. Recommended direction before editing HTML

Recommendation: convert `docs/rolling-spec.html` from the current slide deck into **Option A: Linear operating spec with sticky architecture rail**.

Rationale through StormDeck lenses:

- Radar meteorologist: linear sections make provenance, coverage, and QC caveats harder to miss.
- PAR/radar systems engineer: pipeline and data-level assumptions can be stated explicitly instead of hidden in slide text.
- Scientific visualization engineer: visible labels for synthetic/observed/interpolated/derived can stay persistent.
- Game-engine rendering engineer: MWE acceptance criteria and GPU/data-contract details become easier to implement against.
- Real-time backend engineer: synthetic/archive/live handoff is clearer as a data pipeline.
- Forecaster/operator UX designer: reduces cognitive load; next action and gate remain visible.
- Emergency/public-safety reviewer: risk/uncertainty language is more visible, less “cool radar toy.”

## 8. Proposed new source-of-truth structure

Keep:

- `docs/bryan-inputs.md` as stakeholder/input recall log.
- `docs/atd-data-references.md` as technical radar reference.
- `docs/conversation-digest-2026-05-21.md` as this working conversation digest.

Change:

- `docs/rolling-spec.html` should become the readable living operating spec.

Optional later:

- Add `docs/spec-deck.html` only if a presentation-style artifact is still wanted.

## 9. Immediate next discussion question

Before editing the HTML, decide which format Jon wants:

1. Linear operating spec with sticky architecture rail. Recommended.
2. Architecture dossier with one section per node.
3. Two artifacts: readable living spec plus separate presentation deck.

PARtner recommendation: choose #1 now; add #3 later only if a demo deck is actually needed.
