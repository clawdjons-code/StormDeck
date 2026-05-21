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

## Revision v0.2

The spec now includes a step-by-step failure-mode section and gates for case selection, THREDDS download, CfRadial parsing, ATD sector coverage, geospatial validation, QC/artifacts, rendering, timeline deltas, semantic objects, UX, and exports.
