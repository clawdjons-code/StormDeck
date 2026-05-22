from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VIEWER = ROOT / "viewer" / "index.html"


def test_viewer_scaffold_exists_and_loads_core_exports():
    html = VIEWER.read_text(encoding="utf-8")

    assert "StormDeck Replay Cockpit" in html
    assert "case_timeline.json" in html
    assert "temporal_tracks.json" in html
    assert "change_summary.json" in html
    assert "stormdeck.case_timeline.v0" in html
    assert "stormdeck.temporal_tracks.v0" in html
    assert "stormdeck.change_summary.v0" in html


def test_viewer_surfaces_operational_metadata_and_caveats():
    html = VIEWER.read_text(encoding="utf-8")

    required_ids = [
        'id="case-summary"',
        'id="track-list"',
        'id="change-panel"',
        'id="quarantine-lane"',
        'id="warnings"',
        'id="provenance"',
        'id="source-status"',
    ]
    for required_id in required_ids:
        assert required_id in html

    required_phrases = [
        "Observed metadata only",
        "Radar field deltas not computed",
        "Quarantined transition fragments",
        "Compare only within the same track",
        "Native RHI",
        "scan age",
        "data source",
        "confidence",
        "uncertainty",
    ]
    for phrase in required_phrases:
        assert phrase in html


def test_viewer_has_local_file_controls_for_wea_fs_exports():
    html = VIEWER.read_text(encoding="utf-8")

    assert 'type="file"' in html
    assert 'data-json-role="case_timeline"' in html
    assert 'data-json-role="temporal_tracks"' in html
    assert 'data-json-role="change_summary"' in html
    assert 'data-json-role="field_preview"' in html
    assert 'data-json-role="map_overlays"' in html
    assert "FileReader" in html
    assert "renderCaseSummary" in html
    assert "renderTrackList" in html
    assert "renderChangePanel" in html
    assert "renderFieldPreview" in html


def test_viewer_surfaces_observed_radar_field_preview_without_claiming_3d():
    html = VIEWER.read_text(encoding="utf-8")

    assert "stormdeck.field_preview.v0" in html
    assert 'id="field-preview"' in html
    assert 'id="field-preview-canvas"' in html
    assert 'id="field-preview-legend"' in html
    assert "Observed radar field sample" in html
    assert "native polar sweep" in html
    assert "not a gridded volume" in html
    assert "drawNativePolarPreview" in html
    assert "renderFieldLegend" in html


def test_viewer_uses_atd_reflectivity_palette_and_compact_metadata():
    html = VIEWER.read_text(encoding="utf-8")

    assert "ATD_REFLECTIVITY_STOPS" in html
    for tick in ["90", "80", "70", "60", "50", "40", "30", "20", "10", "0", "-10", "-20", "-30"]:
        assert f"value: {tick}" in html
    for phrase in ["Scan:", "Radials:", "Elevation:", "Time:"]:
        assert phrase in html


def test_viewer_rounds_numeric_field_values_for_operator_readability():
    html = VIEWER.read_text(encoding="utf-8")

    assert "fmtNumber(stats.min, 1)" in html
    assert "fmtNumber(stats.max, 1)" in html
    assert "Elevation span:" in html
    assert "~" in html


def test_viewer_derives_elevation_metadata_from_legacy_coordinate_arrays():
    html = VIEWER.read_text(encoding="utf-8")

    assert "deriveElevationDisplay(preview)" in html
    assert "preview.coordinates?.elevation_deg" in html
    assert "roundTenth" in html
    assert "fixed_angle_label" in html


def test_viewer_adds_non_gridded_map_context_for_native_sector():
    html = VIEWER.read_text(encoding="utf-8")

    assert 'id="map-context-canvas"' in html
    assert 'id="map-context-summary"' in html
    assert "drawMapContext" in html
    assert "sector outline only" in html
    assert "not gridded" in html
    assert "radar site marker" in html


def test_viewer_map_context_has_orientation_and_range_sketch_labels():
    html = VIEWER.read_text(encoding="utf-8")

    assert "drawOrientationCompass" in html
    assert "drawRangeRings" in html
    assert "labelSectorBoundary" in html
    assert "orientation sketch only" in html
    assert "range rings" in html
    for label in ["'N'", "'E'", "'S'", "'W'"]:
        assert label in html


def test_viewer_supports_map_overlays_contract_without_gridding_radar():
    html = VIEWER.read_text(encoding="utf-8")

    assert "map_overlays.json" in html
    assert "stormdeck.map_overlays.v0" in html
    assert "drawMapOverlays" in html
    assert "projectLatLonToSketch" in html
    assert "warning_corridor" in html
    assert "town_points" in html
    assert "county_boundaries" in html
    assert "state_boundaries" in html
    assert "context overlays only" in html


def test_viewer_reports_structured_overlay_layer_counts_and_legend():
    html = VIEWER.read_text(encoding="utf-8")

    assert "countMapOverlayLayers" in html
    assert "renderOverlayLegend" in html
    assert "Towns</span>" in html
    assert "Warning corridors</span>" in html
    assert "County boundaries</span>" in html
    assert "State boundaries</span>" in html
    assert "overlay-legend" in html
    assert "town point" in html
    assert "warning corridor" in html


def test_viewer_declutters_town_labels_without_hiding_town_points():
    html = VIEWER.read_text(encoding="utf-8")

    assert "drawTownPoint" in html
    assert "placeTownLabel" in html
    assert "labelBoxes" in html
    assert "label_priority" in html
    assert "Town labels are decluttered" in html
    assert "leader line" in html


def test_viewer_uses_local_overlay_scale_and_readable_warning_corridors():
    html = VIEWER.read_text(encoding="utf-8")

    assert "computeOverlaySketchScale" in html
    assert "collectOverlayPoints" in html
    assert "drawWarningCorridor" in html
    assert "placeCorridorLabel" in html
    assert "local impact scale" in html
    assert "Warning corridor geometry is schematic context" in html
    assert "lineWidth = 2.4" in html


def test_viewer_has_map_focus_mode_toggle_for_full_sector_and_local_impact():
    html = VIEWER.read_text(encoding="utf-8")

    assert "mapFocusMode" in html
    assert "data-map-focus-mode" in html
    assert "Full sector" in html
    assert "Local impact" in html
    assert "resolveMapFocusScale" in html
    assert "setMapFocusMode" in html
    assert "full radar sector scale" in html
    assert "local impact scale" in html


def test_viewer_uses_stacked_overlay_counts_and_clarifies_not_gridded():
    html = VIEWER.read_text(encoding="utf-8")

    assert "overlay-count-grid" in html
    assert "Towns</span>" in html
    assert "Warning corridors</span>" in html
    assert "County boundaries</span>" in html
    assert "State boundaries</span>" in html
    assert "radar gates not gridded" in html
    assert "visual guide grid only" in html


def test_viewer_supports_field_preview_playlist_scrubber_and_change_ghosts():
    html = VIEWER.read_text(encoding="utf-8")

    assert "field_preview_playlist" in html
    assert "stormdeck.field_preview_playlist.v0" in html
    assert "field-preview-playlist" in html
    assert "frame-scrubber" in html
    assert "setFrameIndex" in html
    assert "toggleFramePlayback" in html
    assert "drawPreviousFrameGhost" in html
    assert "computeFrameDeltaStats" in html
    assert "change ghost" in html
    assert "not motion interpolation" in html
    assert "frame playlist" in html


def test_viewer_batches_animation_and_2_5d_controls_with_honesty_language():
    html = VIEWER.read_text(encoding="utf-8")

    assert "sceneMode" in html
    assert "data-scene-mode" in html
    assert "Native polar" in html
    assert "2.5D slab" in html
    assert "toggleAnimation" in html
    assert "requestAnimationFrame" in html
    assert "drawScanSweepOverlay" in html
    assert "drawTwoPointFiveDSlabPreview" in html
    assert "scene-tilt-slider" in html
    assert "vertical-exaggeration-slider" in html
    assert "not a vertical retrieval" in html
    assert "observed gates extruded for visual emphasis" in html


def test_viewer_layout_prevents_long_labels_from_jumping_tracks():

    html = VIEWER.read_text(encoding="utf-8")

    assert "minmax(0, 1fr)" in html
    assert ".panel, .track, .metric, ul.clean li" in html
    assert "overflow-wrap: anywhere" in html
    assert "word-break: break-word" in html
    assert "@media (max-width: 1280px)" in html
