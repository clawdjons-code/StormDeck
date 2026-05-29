import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COCKPIT = ROOT / "viewer" / "stormdeck_cockpit_ui.html"


def read_html():
    return COCKPIT.read_text(encoding="utf-8")


def test_stormdeck_cockpit_ui_exists_and_has_approved_view_labels():
    html = read_html()

    assert "StormDeck" in html
    assert "2.5D Browser Replay" in html
    assert "4D View Concept" in html
    assert "Vertical A–B Cross Section" in html
    assert "What changed last 60 sec" in html
    assert "QC / Provenance" in html
    assert "Screenshot" in html
    assert "Video" in html


def test_stormdeck_cockpit_ui_includes_only_current_build_feature_contracts():
    html = read_html()

    required = [
        "native radar sector/map",
        "range rings",
        "warning corridor",
        "A–B cross-section line",
        "Field",
        "Sweep",
        "Scan age",
        "Observed",
        "Interpolated",
        "No data",
        "Provenance",
        "Storm Object — inferred",
        "compact timeline",
    ]
    for phrase in required:
        assert phrase in html


def test_stormdeck_cockpit_ui_avoids_disallowed_scope_creep():
    html = read_html().lower()

    literal_disallowed = [
        "sensors",
        "live network",
        "gpu temp",
        "vram",
        "gpu buffer",
        "hardware dashboard",
        "warn-on-forecast",
        "+10 min",
        "time ghost",
        "updraft",
        "rear inflow",
        "hail",
        "tornado warning count",
        "email",
        "avatar",
        "account",
    ]
    for phrase in literal_disallowed:
        assert phrase not in html

    for product in ["hrrr", "gfs", "nam"]:
        assert re.search(rf"\b{product}\b", html) is None


def test_stormdeck_cockpit_ui_has_view_focused_structure_and_canvas_hooks():
    html = read_html()

    for element_id in [
        "replayFieldCanvas",
        "replayMap",
        "crossSection",
        "futureView",
        "timelineScrubber",
        "fieldSelect",
        "sweepSelect",
        "scanAgeBadge",
        "whatChangedPanel",
        "qcProvenancePanel",
        "exportPanel",
    ]:
        assert f'id="{element_id}"' in html

    for helper in [
        "drawReplayMap",
        "drawCrossSection",
        "drawFutureView",
        "drawRangeRings",
        "drawWarningCorridor",
        "drawReflectivityCore",
    ]:
        assert helper in html


def test_2_5d_window_has_clarity_affordances():
    html = read_html()

    for element_id in [
        "latestTimeLabel",
        "selectedSliceLabel",
        "radarOriginLabel",
        "replayViewScope",
    ]:
        assert f'id="{element_id}"' in html

    for phrase in [
        "Latest scan age",
        "Sweep / elevation",
        "Selected A–B slice",
        "Radar origin",
        "Observed gates",
        "Interpolated guide",
        "Current time · 20:11:24Z",
        "2.5D clarity pass",
    ]:
        assert phrase in html


def test_adaptive_view_sizing_sliders_are_available_and_stateful():
    html = read_html()

    for element_id in [
        "adaptiveSizingPanel",
        "replayWidthSlider",
        "crossHeightSlider",
        "bottomCardSlider",
        "resetLayoutButton",
    ]:
        assert f'id="{element_id}"' in html

    for phrase in [
        "Adaptive view sizing",
        "2.5D width",
        "Slice height",
        "Card row",
        "Reset layout",
    ]:
        assert phrase in html

    for css_var in [
        "--replay-fr",
        "--future-fr",
        "--cross-row",
        "--bottom-row",
        "--mobile-replay-row",
        "--mobile-future-row",
        "--mobile-bottom-card-row",
    ]:
        assert css_var in html

    for js_hook in [
        "applyAdaptiveLayout",
        "replayWidthSlider.addEventListener",
        "crossHeightSlider.addEventListener",
        "bottomCardSlider.addEventListener",
        "resetLayoutButton.addEventListener",
        "mobileReplayRow",
        "--mobile-replay-row",
        "--mobile-future-row",
        "--mobile-bottom-card-row",
    ]:
        assert js_hook in html


def test_adaptive_sizing_controls_have_mobile_touch_layout():
    html = read_html()

    assert 'name="viewport"' in html
    assert "width=device-width" in html
    assert "initial-scale=1" in html

    for css_contract in [
        "@media (max-width: 760px)",
        "flex-wrap: wrap",
        "touch-action: pan-y",
        ".adaptive-sizing { grid-column: 1 / -1",
        ".adaptive-sizing { min-width: 100%",
        ".slider-field { grid-template-columns: 76px minmax(120px, 1fr) 34px",
        "main { grid-template-columns: minmax(0, 1fr)",
        "grid-template-rows: var(--mobile-replay-row) var(--cross-row) var(--mobile-future-row)",
        "grid-auto-rows: var(--mobile-bottom-card-row)",
    ]:
        assert css_contract in html


def test_reflectivity_legend_is_docked_not_overlaying_2_5d_view():
    html = read_html()

    assert 'class="replay-workspace"' in html
    assert 'class="legend-card legend-dock"' in html
    assert 'id="quicklookDock"' in html
    assert 'id="quicklookThumb"' in html
    assert 'quicklook PNG kept as reference only' in html
    assert 'grid-template-columns: minmax(0, 1fr) 156px' in html
    assert 'grid-template-columns: 1fr' in html
    assert 'grid-row: 2' in html
    assert 'grid-column: 2' in html
    assert 'grid-column: 1' in html

    legend_block = re.search(r"\.legend-card \{(?P<body>.*?)\n    \}", html, re.S)
    assert legend_block is not None
    assert "position: absolute" not in legend_block.group("body")

    mobile_legend_rules = [
        line.strip()
        for line in html.splitlines()
        if line.strip().startswith(".legend-dock")
    ]
    assert mobile_legend_rules
    for rule in mobile_legend_rules:
        assert "position: absolute" not in rule
        assert "transform:" not in rule


def test_cockpit_is_manifest_ready_and_data_honest_before_real_data():
    html = read_html()

    for contract in [
        'id="bundleRootInput"',
        'id="loadBundleButton"',
        'id="manifestStatus"',
        'const cockpitState',
        'loadCockpitBundle',
        'fetchJson',
        'applyManifestToCockpit',
        'populateFieldAndSweepSelectorsFromManifest',
        'currentFrame',
        'stormdeck_bundle_manifest.json',
        'bundle_validation.json',
    ]:
        assert contract in html

    for honest_phrase in [
        "Change panel unavailable until comparable frame deltas are loaded.",
        "No meteorological 60-sec delta available",
        "sample browse only — not time-continuous storm motion",
        "2.5D visual emphasis; observed-gate source; not full volume retrieval",
        "Transform status",
        "field_value_deltas_included: false",
        "QC pending",
        "missing/flag counts required",
        "Export embeds radar ID, field, units, time, source, and transform status",
    ]:
        assert honest_phrase in html

    for forbidden_claim in [
        "Reflectivity core shifted slightly along A–B.",
        "Warning corridor overlay updated with the latest replay frame.",
        "Pass</b><span>basic QC",
        "Velocity (kt)",
        "inbound / outbound",
        "Waco",
        "College Station",
        "Topeka",
        "Lawrence",
    ]:
        assert forbidden_claim not in html

    for required_geography in ["Norman", "Moore", "Noble", "Purcell", "Chickasha", "Shawnee"]:
        assert required_geography in html

    assert "Velocity (m/s)" in html
    assert "velocityScale" in html
    assert "linear-gradient(180deg, #3b60ff" in html or "linear-gradient(90deg, #3b60ff" in html


def test_cockpit_real_manifest_contract_handles_ref_vel_sw_quicklooks_and_qc_honestly():
    html = read_html()

    for contract in [
        "const fieldVocabulary",
        "REF: { label: 'Reflectivity', units: 'dBZ'",
        "VEL: { label: 'Velocity', units: 'm/s'",
        "SW: { label: 'Spectrum width', units: 'm/s'",
        "fieldInfo(",
        "renderObservedQuicklookFrame",
        "renderQuicklookDock",
        "quicklook_exists",
        "quicklook_path",
        "observed_native_quicklook_reference_only",
        "quicklook PNG kept as reference only",
        "mock_visual_guide_not_real_data",
        "QC pending",
        "missing/flag counts required",
        "renderTimelineTicksFromFrames",
        "volume_start_time",
        "manifestVolumeOrdinals",
        "syncCurrentFrameToSelection",
        "currentVolumeOrdinal",
        "Replay volume",
    ]:
        assert contract in html

    for forbidden in [
        "includes('velocity')",
        'units: fieldSelect.value.toLowerCase().includes',
        "validation.status || 'validated bundle'",
    ]:
        assert forbidden not in html


def test_visible_controls_have_real_behavior_hooks():
    html = read_html()

    for element_id in [
        "playReplayButton",
        "playbackStatus",
        "legendTitle",
        "screenshotButton",
        "videoButton",
        "exportStatus",
    ]:
        assert f'id="{element_id}"' in html

    for handler in [
        "applyFieldAndSweep",
        "togglePlayback",
        "exportReplaySvg",
        "exportStoryboardJson",
        "fieldSelect.addEventListener('change'",
        "sweepSelect.addEventListener('change'",
        "playReplayButton.addEventListener('click'",
        "screenshotButton.addEventListener('click'",
        "videoButton.addEventListener('click'",
    ]:
        assert handler in html

    for status_phrase in [
        "Paused · playback 1×",
        "Screenshot SVG ready",
        "Video storyboard JSON ready",
    ]:
        assert status_phrase in html


def test_ab_slice_is_manipulatable_and_data_honest():
    html = read_html()

    for element_id in [
        "sliceModeSelect",
        "sliceInterpSelect",
        "sliceStatus",
    ]:
        assert f'id="{element_id}"' in html

    for dynamic_svg_id in [
        "sliceHandleA",
        "sliceHandleB",
        "sliceLineActive",
    ]:
        assert dynamic_svg_id in html

    for phrase in [
        "Slice",
        "Free drag",
        "Storm-relative",
        "Motion-vector",
        "Warning-corridor",
        "Interpolation",
        "nearest gates",
        "smoothed guide",
        "mode: observed gates + interpolated guide",
        "drag A/B handles",
        "no-data mask",
    ]:
        assert phrase in html

    for handler in [
        "const sliceState",
        "drawSliceControls",
        "updateSliceFromPointer",
        "setActiveSliceHandle",
        "pointerdown",
        "pointermove",
        "pointerup",
        "sliceModeSelect.addEventListener('change'",
        "sliceInterpSelect.addEventListener('change'",
    ]:
        assert handler in html


def test_ab_slice_handles_have_large_user_hit_targets_and_keyboard_fallback():
    html = read_html()

    for hit_target_id in [
        "sliceHandleAHitTarget",
        "sliceHandleBHitTarget",
    ]:
        assert hit_target_id in html

    for contract in [
        "r:34",
        "fill:'transparent'",
        "pointer-events':'all'",
        "touchAction = 'none'",
        "userSelect = 'none'",
        "bindSliceHandleTarget",
        "handleSliceKeyboardNudge",
        "keydown",
        "Dragging A handle",
        "Dragging B handle",
    ]:
        assert contract in html



def test_cockpit_promotes_field_preview_canvas_over_quicklook_png():
    html = read_html()

    for contract in [
        'id="replayFieldCanvas"',
        'currentFieldPreview',
        'previousFieldPreview',
        'renderPrimaryFieldLayer',
        'drawNativePolarPreview',
        'drawTwoPointFiveDSlabPreview',
        'drawPreviousFrameGhost',
        'drawScanSweepOverlay',
        'colorForField',
        'atdReflectivityColor',
        'stormdeck.field_preview.v0',
        'stormdeck.field_preview_playlist.v0',
        'observed-gate field_preview primary layer',
        'observed_field_preview_sampled_gates',
        'quicklook PNG kept as reference only',
    ]:
        assert contract in html

    assert "primary layer is field_preview sampled gates" in html


def test_cockpit_renders_meaningful_map_overlays_from_export():
    html = read_html()

    for contract in [
        'mapOverlays',
        'loadOptionalCockpitArtifacts',
        'map_overlays.json',
        'stormdeck.map_overlays.v0',
        'projectLatLonToSketch',
        'drawMapOverlays',
        'drawOverlayPolyline',
        'drawTownPoint',
        'placeTownLabel',
        'countMapOverlayLayers',
        'warning corridor geometry is schematic context',
        'radar gates not gridded',
        'context overlays only',
    ]:
        assert contract in html


def test_cockpit_labels_cross_section_and_4d_as_concept_not_loaded_data():
    html = read_html()

    for contract in [
        'native RHI observed gates when vertical_slice loads · otherwise concept guide only',
        'concept guide only · not generated from loaded radar data',
        'concept only · not generated from loaded radar data',
        '4D concept view is not generated from loaded radar data yet',
        'Cross-section/4D are concept only, not generated from loaded radar data',
    ]:
        assert contract in html


def test_cockpit_can_render_native_rhi_vertical_slice_sidecar():
    html = read_html()

    for contract in [
        'verticalSlicePlaylist',
        'verticalSlice',
        'vertical_slice_playlist.json',
        'vertical_slice.json',
        'stormdeck.vertical_slice_playlist.v0',
        'stormdeck.vertical_slice.v0',
        'currentVerticalSlice',
        'renderVerticalSliceCrossSection',
        'native RHI observed gates',
        'not arbitrary A-B interpolation',
        'observed_native_rhi_vertical_slice_sampled_gates',
    ]:
        assert contract in html
