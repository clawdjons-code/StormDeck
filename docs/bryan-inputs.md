# Bryan Inputs — StormDeck Recall Log

Purpose: preserve all StormDeck-relevant information Bryan provides, in a compact Markdown file sorted for reliable future recall by humans and agents.

Update rule: whenever Bryan provides a new requirement, constraint, preference, correction, hardware detail, dataset clue, research context, or decision, append it to the appropriate section below and add a dated entry to the changelog. Do not bury Bryan-provided facts only in chat transcripts.

Last updated: 2026-05-21 17:16 CDT

## 0. Current distilled guidance

- Build a minimum working example before real-data ingest.
- The MWE should be an app using a game engine to render a 3D display of simulated reflectivity data.
- Hard-code as many parameters as needed for the first version.
- After the synthetic/game-engine MWE works, feed the engine more realistic archived data.
- After archived-data replay works, wire up a live stream of actual weather data from an operational PAR.
- A PC with RTX 4090 and 128 GB RAM is an expected/available high-end prototype target.

## 1. Direct Bryan messages

### 2026-05-21 — MWE-first build order

Quoted/paraphrased from Bryan via Jon:

> Great! Howdy Bart- I mean PARtner.
>
> I’m interested in getting an MWE (minimum working example) going where we can see an app that uses a game engine to render a 3D display of simulated reflectivity data (hard-coding as many parameters as necessary). Then we can worry about feeding the engine more realistic archived data. After that, we can worry about wiring up a live stream of actual weather data from an operational PAR.

Operational interpretation:

- Treat the first deliverable as a synthetic reflectivity renderer, not a radar-ingest project.
- Rendering and interaction contract comes before archive parsing.
- Live operational PAR stream is explicitly later-stage, not an MVP dependency.

## 2. Hardware inputs and assumptions from Bryan/Jon thread

### 2026-05-21 — Prototype workstation

Input:

- Candidate machine: PC with RTX 4090 and 128 GB RAM.

Assessment recorded in rolling spec:

- More than enough for synthetic MWE.
- Good high-end workstation target for early archived replay.
- Likely bottleneck is software/data pipeline, not GPU/RAM.
- Initial target volume: `256 × 256 × 64`, 30–120 frames, reflectivity first, velocity second.

Open hardware details to request later:

- CPU model.
- Storage type and available capacity, preferably NVMe SSD.
- Operating system/version.
- Preferred engine install state: Unreal Engine, Unity, or neither.
- Whether the machine will be used for development, demo only, or both.

## 3. Decisions derived from Bryan inputs

### D1 — Synthetic before archived radar

- Status: accepted for near-term plan.
- Reason: proves the renderer, UI, data contract, and GPU strategy before spending effort on radar format complexity.
- Consequence: `docs/rolling-spec.html` now treats synthetic game-engine MWE as current gate.

### D2 — Game engine app, not notebook-only visualization

- Status: accepted.
- Reason: Bryan specifically asked for an app using a game engine.
- Consequence: Python notebooks/scripts may generate data, but the demonstration target is an interactive engine-rendered app.

### D3 — Hard-code early parameters

- Status: accepted.
- Reason: reduces uncertainty and avoids premature generalization.
- Consequence: fixed radar origin/grid/color map/storm motion are allowed in MWE if metadata records them clearly.

## 4. Open Bryan follow-ups

Ask Bryan when useful, not before making obvious progress:

1. Preferred first engine: Unreal Engine 5, Unity, or fastest available local prototype?
2. Should the first MWE be native desktop only, or should it also be browser-shareable?
3. Is the 4090 PC available for hands-on dev/builds, or just target hardware for demo?
4. Does Bryan have a specific operational PAR source in mind for the live-stream phase?
5. Are there archived cases Bryan particularly wants represented after synthetic MWE works?

## 5. Recall keywords

Use these terms to find this file later:

- Bryan
- MWE
- minimum working example
- game engine
- simulated reflectivity
- synthetic reflectivity
- hard-coded parameters
- archived data later
- live operational PAR later
- RTX 4090
- 128 GB RAM

## 6. Changelog

### 2026-05-21 17:16 CDT

- Created Bryan recall log.
- Added Bryan’s MWE-first message, hardware context, derived decisions, and follow-up questions.
