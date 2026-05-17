# StormDeck Failure-Mode Review

Revision date: 2026-05-16

StormDeck’s hardest failure mode is not inability to render radar data. The real risk is producing a visually compelling interface that overstates what the ATD data actually observed. The v0 build should therefore be gated by data-truth checks before renderer polish.

## Top serious risks

1. Misrepresenting ATD sector data as fuller coverage than it is.
2. Bad coordinate transforms/geospatial misalignment.
3. Velocity aliasing or QC artifacts interpreted as meteorology.
4. Choosing a weak or messy public case.
5. Overbuilding live/PAR/adaptive features before replay works.
6. Naive interpolation creating fake 3D structure.
7. GPU memory/performance collapse from too much volume data.
8. UX that impresses but slows warning decisions.
9. Semantic objects appearing more authoritative than their source.
10. Timeline/delta logic ignoring irregular scan timing.

## Revised safest build order

1. Case scanner: find, download-check, and score ATD cases.
2. CfRadial truth reporter: inspect real metadata and fields.
3. Native PPI viewer: render observed reflectivity/velocity only.
4. Geospatial validation: radar site, range rings, towns, sector mask.
5. Timeline replay: actual timestamps and irregular intervals preserved.
6. Slice prototype: clearly label native vs interpolated views.
7. Manual storm object: source-labeled and confidence-labeled.
8. 60-second delta panel: conservative, evidence-linked, actual interval shown.
9. Render cache/GPU optimization: only after data model is trusted.
10. Demo export: baked provenance/QC labels.

## Required gates

- No renderer work consumes a file until the truth reporter emits geometry, field, time-span, and QC metadata.
- No 3D/gridded view is shown without an observed mask and interpolation label.
- No semantic object is displayed without source, confidence, time span, and derived/observed status.
- No timeline delta is shown without the actual comparison interval.
- No screenshot/video export is allowed without timestamp, radar ID, field, source, and QC/provenance label.
