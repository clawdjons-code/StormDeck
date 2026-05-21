# Bryan Inputs — StormDeck Recall Log

Purpose: preserve every StormDeck-relevant message or input Bryan provides, in Markdown sorted for reliable future recall by humans and agents.

Update rule: whenever Bryan provides a new requirement, constraint, preference, correction, hardware detail, dataset clue, research context, or decision, append it to the correct section below and add a dated changelog entry. Do not bury Bryan-provided facts only in chat transcripts.

Last updated: 2026-05-21 17:34 CDT

## 0. Coverage status

As of 2026-05-21 17:34 CDT, the only direct Bryan message available in this repo/chat context is the MWE-first message relayed by Jon on 2026-05-21. It is quoted in full below. No other direct Bryan technical messages have been provided yet in this chat context.

Related but not direct-Bryan input: Jon asked whether a PC with RTX 4090 and 128 GB RAM would run the MWE. That hardware context is recorded separately in Section 3 because it affects architecture, but it is not labeled as a direct Bryan quote.

## 1. Current distilled Bryan guidance

- Build a minimum working example before real-data ingest.
- The MWE should be an app using a game engine to render a 3D display of simulated reflectivity data.
- Hard-code as many parameters as needed for the first version.
- After the synthetic/game-engine MWE works, feed the engine more realistic archived data.
- After archived-data replay works, wire up a live stream of actual weather data from an operational PAR.

## 2. Direct Bryan messages

### 2026-05-21 — MWE-first build order

Source: quoted by Jon in the PARtalk Telegram thread.

Full message:

> Great! Howdy Bart- I mean PARtner.
>
> I’m interested in getting an MWE (minimum working example) going where we can see an app that uses a game engine to render a 3D display of simulated reflectivity data (hard-coding as many parameters as necessary). Then we can worry about feeding the engine more realistic archived data. After that, we can worry about wiring up a live stream of actual weather data from an operational PAR.

Operational interpretation:

- Treat the first deliverable as a synthetic reflectivity renderer, not a radar-ingest project.
- Rendering and interaction contract comes before archive parsing.
- Live operational PAR stream is explicitly later-stage, not an MVP dependency.
- The first demo may hard-code grid, radar origin, color ramp, synthetic storm motion, timestamps, and data source as long as those assumptions are visible in metadata.

Architecture implications:

- Use a staged pipeline: synthetic source → metadata contract → preprocessing/cache → engine renderer → operator tools → archived adapter → live adapter.
- Keep the MWE data contract close enough to real radar metadata that archived data can replace the synthetic source without rewriting the renderer.

## 3. Related hardware context from Jon/Bryan thread

### 2026-05-21 — Prototype workstation question

Input source: Jon asked whether a PC with RTX 4090 and 128 GB RAM would run it.

Assessment recorded in rolling spec:

- Yes; this machine is more than enough for the synthetic MWE.
- It is a strong high-end workstation target for early archived replay.
- Likely bottleneck is software/data pipeline, not GPU/RAM.
- Initial target volume: `256 × 256 × 64`, 30–120 frames, reflectivity first, velocity second.

Open hardware details to request later:

- CPU model.
- Storage type and available capacity, preferably NVMe SSD.
- Operating system/version.
- Preferred engine install state: Unreal Engine, Unity, or neither.
- Whether the machine will be used for development, demo only, or both.

## 4. Decisions derived from Bryan inputs

### D1 — Synthetic before archived radar

- Status: accepted for near-term plan.
- Reason: proves the renderer, UI, data contract, and GPU strategy before spending effort on radar format complexity.
- Consequence: `docs/rolling-spec.html` treats synthetic game-engine MWE as the current gate.

### D2 — Game engine app, not notebook-only visualization

- Status: accepted.
- Reason: Bryan specifically asked for an app using a game engine.
- Consequence: Python scripts may generate data, but the demonstration target is an interactive engine-rendered app.

### D3 — Hard-code early parameters

- Status: accepted.
- Reason: reduces uncertainty and avoids premature generalization.
- Consequence: fixed radar origin/grid/color map/storm motion are allowed in the MWE if metadata records them clearly.

### D4 — Architecture-map-first spec

- Status: accepted per Jon’s follow-up.
- Reason: the spec should focus on the system architecture path, with clickable nodes exposing details.
- Consequence: `docs/rolling-spec.html` now makes the clickable system architecture map the main focus instead of the previous topographic map.

## 5. Latest recommendation to Bryan / StormDeck team

Recommended current architecture:

1. **Synthetic Reflectivity Source** — deterministic generator emits 30–120 frames of plausible storm reflectivity.
2. **Metadata/Data Contract** — every frame carries timestamp, source, field, units, grid, truth status, and payload reference.
3. **Preprocess + Render Cache** — convert frames to GPU-friendly 3D textures while preserving metadata.
4. **Game-Engine Renderer** — Unreal-first unless team velocity favors Unity; render volume/slices with metadata HUD.
5. **Operator Interaction Layer** — timeline scrub, horizontal/vertical slices, storm motion arrow, change panel, screenshot/video export.
6. **Archived Radar Adapter** — later module maps ATD/NEXRAD data into the same contract.
7. **Live PAR Adapter** — final module streams operational data after replay contract is stable.

Smallest next action:

- Generate 30 synthetic `256 × 256 × 64` reflectivity frames plus metadata JSON, then load one frame into the selected engine and display it with a labeled dBZ color map.

## 6. Open Bryan follow-ups

Ask Bryan when useful, not before making obvious progress:

1. Preferred first engine: Unreal Engine 5, Unity, or fastest available local prototype?
2. Should the first MWE be native desktop only, or should it also be browser-shareable?
3. Is the 4090 PC available for hands-on dev/builds, or just target hardware for demo?
4. Does Bryan have a specific operational PAR source in mind for the live-stream phase?
5. Are there archived cases Bryan particularly wants represented after synthetic MWE works?

## 7. Recall keywords

- Bryan
- MWE
- minimum working example
- game engine
- simulated reflectivity
- synthetic reflectivity
- hard-coded parameters
- archived data later
- live operational PAR later
- system architecture map
- RTX 4090
- 128 GB RAM

## 8. Changelog

### 2026-05-21 17:34 CDT

- Explicitly marked the coverage status: only one direct Bryan message is available so far.
- Separated direct Bryan quote from Jon-provided hardware context.
- Added the latest architecture recommendation and system-architecture-map decision.

### 2026-05-21 17:16 CDT

- Created Bryan recall log.
- Added Bryan’s MWE-first message, hardware context, derived decisions, and follow-up questions.
