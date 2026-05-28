from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VIEWER = ROOT / "viewer" / "ppi_bundle_viewer.html"


def test_ppi_bundle_viewer_exists_and_targets_replay_index():
    html = VIEWER.read_text(encoding="utf-8")

    assert "StormDeck PPI Sample Bundle Browser" in html
    assert "ppi_tprt_replay_index.json" in html
    assert "stormdeck.ppi_replay_index.v0" in html
    assert "volumes/<volume_id>/quicklooks/<sweep>_<field>.png" in html
    assert "manifest.json" in html


def test_ppi_bundle_viewer_maps_volume_file_to_manifest_and_quicklook_paths():
    html = VIEWER.read_text(encoding="utf-8")

    assert "volumeIdFromFile" in html
    assert ".replace(/\\.nc$/i, '')" in html
    assert "joinPath(bundleState.root, 'volumes', volumeId, 'manifest.json')" in html
    assert "joinPath(bundleState.root, 'volumes', bundleState.volumeId, 'quicklooks'" in html
    assert "`${bundleState.sweep}_${bundleState.field}.png`" in html


def test_ppi_bundle_viewer_enforces_operational_caveats_and_no_delta_claims():
    html = VIEWER.read_text(encoding="utf-8")

    required = [
        "sample/browse bundle",
        "not a time-continuous storm sequence",
        "do not interpret frame changes as storm motion",
        "RHI scans are intentionally excluded",
        "not gridded 3D volume rendering",
        "not meteorological temporal deltas",
    ]
    for phrase in required:
        assert phrase in html


def test_ppi_bundle_viewer_has_operator_controls_and_keyboard_navigation():
    html = VIEWER.read_text(encoding="utf-8")

    for element_id in ["bundleRoot", "loadBundle", "volumeSelect", "fieldSelect", "sweepSelect", "imageFrame", "metadataPanel"]:
        assert f'id="{element_id}"' in html
    for field in ["REF", "VEL", "SW"]:
        assert f"<option>{field}</option>" in html
    assert "ArrowLeft" in html
    assert "ArrowRight" in html
    assert "ArrowUp" in html
    assert "ArrowDown" in html
    assert "event.key === ' '" in html


def test_ppi_bundle_viewer_adds_forecaster_readability_polish():
    html = VIEWER.read_text(encoding="utf-8")

    for helper in [
        "formatAngleDeg",
        "formatRangeKm",
        "formatSweepPosition",
        "renderFieldLegend",
        "FIELD_LEGENDS",
    ]:
        assert helper in html
    assert "0.5° elevation" in html
    assert "441.1 km" in html
    assert "Sweep 1 of 14" in html
    assert "Reflectivity color guide" in html
    assert "Velocity color guide" in html
    assert "Spectrum width guide" in html


def test_ppi_bundle_viewer_exposes_browse_vs_replay_and_path_copy_controls():
    html = VIEWER.read_text(encoding="utf-8")

    assert "PPI Sample Bundle Browser" in html
    assert "copyQuicklookPath" in html
    assert "copy quicklook path" in html
    assert "title=\"Full volume identifier" in html
    assert "Load ppi_tprt_replay_index.json" in html


def test_ppi_bundle_viewer_has_zoom_fit_overlay_and_validation_summary():
    html = VIEWER.read_text(encoding="utf-8")

    for element_id in [
        "fitModeSelect",
        "fullscreenImage",
        "frameOverlay",
        "validationSummary",
        "validationStatusBadge",
    ]:
        assert f'id="{element_id}"' in html
    for text in ["Fit", "Native", "2x", "Fullscreen", "bundle_validation.json"]:
        assert text in html
    for helper in [
        "loadValidationReport",
        "renderValidationSummary",
        "setFitMode",
        "renderFrameOverlay",
    ]:
        assert helper in html
    assert "READY · 2 volumes · 84 quicklooks · 0 missing" in html
    assert "Volume time" in html
    assert "Fixed angle" in html
    assert "Observed quicklook; not gridded" in html


def test_ppi_bundle_viewer_loads_engine_manifest_and_inspects_playlist():
    html = VIEWER.read_text(encoding="utf-8")

    for element_id in [
        "appVersionBadge",
        "manifestSummary",
        "engineManifestBadge",
        "frameInspector",
    ]:
        assert f'id="{element_id}"' in html
    for text in [
        "stormdeck_bundle_manifest.json",
        "Engine manifest",
        "Frame playlist",
        "Godot loader",
        "stormdeck.bundle_manifest.v0",
        "json_plus_relative_png_paths",
        "Frames: 84",
        "StormDeck bundle browser v0.5",
    ]:
        assert text in html
    for helper in [
        "loadEngineManifest",
        "renderEngineManifestSummary",
        "renderFrameInspector",
        "findEngineFrame",
    ]:
        assert helper in html


def test_ppi_bundle_viewer_v04_has_frame_playlist_navigation_and_clear_sweep_indexing():
    html = VIEWER.read_text(encoding="utf-8")

    for element_id in [
        "prevFrame",
        "nextFrame",
        "playlistPosition",
        "playlistStrip",
    ]:
        assert f'id="{element_id}"' in html
    for text in [
        "StormDeck bundle browser v0.5",
        "Frame 1 of 84",
        "Index 0 · Sweep 1 of 14",
        "3x",
        "Frame ←",
        "Frame →",
        "Frame playlist navigation uses stormdeck_bundle_manifest.json order",
    ]:
        assert text in html
    for helper in [
        "currentEngineFrameIndex",
        "selectEngineFrameByIndex",
        "stepFrame",
        "formatSweepIndexLabel",
        "renderPlaylistStrip",
    ]:
        assert helper in html


def test_ppi_bundle_viewer_v05_prioritizes_screenshot_readability():
    html = VIEWER.read_text(encoding="utf-8")

    for text in [
        "StormDeck bundle browser v0.5",
        "Screenshot-readable layout",
        "Center image scale",
        "Browsing order, not storm evolution",
    ]:
        assert text in html

    for css in [
        "font: 16px/1.5",
        "font-size: 22px",
        "padding: 8px 12px",
        "minmax(620px, 1fr)",
        "font-size: 18px",
    ]:
        assert css in html


def test_ppi_bundle_viewer_v05_center_overlay_contains_frame_identity_and_caveat():
    html = VIEWER.read_text(encoding="utf-8")

    for helper in [
        "formatPlaylistPosition",
        "renderFrameOverlay",
        "currentEngineFrameIndex",
    ]:
        assert helper in html

    for text in [
        "Frame ${current + 1} of ${frameCount}",
        "Observed quicklook",
        "sample/browse only",
        "not time-continuous storm motion",
        "Index 0 · Sweep 1 of 14",
    ]:
        assert text in html


def test_ppi_bundle_viewer_v05_playlist_active_frame_is_explicit():
    html = VIEWER.read_text(encoding="utf-8")

    for text in [
        "CURRENT · #",
        "playlist-frame active",
        "Frame playlist navigation uses stormdeck_bundle_manifest.json order",
    ]:
        assert text in html

    for css in [
        "box-shadow: inset 3px 0 0 var(--accent)",
        "font-size: 14px",
    ]:
        assert css in html


def test_ppi_bundle_viewer_v05_current_frame_readouts_show_playlist_position():
    html = VIEWER.read_text(encoding="utf-8")

    for text in [
        "Playlist position",
        "Frame",
        "Field",
        "Sweep",
        "Volume / quicklook",
    ]:
        assert text in html

    assert "formatPlaylistPosition()" in html


def test_ppi_bundle_viewer_v06_has_operator_readiness_panel():
    html = VIEWER.read_text(encoding="utf-8")

    for element_id in [
        "bundleReadinessPanel",
        "readinessValidation",
        "readinessEngineManifest",
        "readinessVolumes",
        "readinessFrames",
        "readinessQuicklooks",
        "readinessMissingQuicklooks",
        "readinessSemanticObjects",
    ]:
        assert f'id="{element_id}"' in html
    for text in [
        "Bundle readiness",
        "Validation",
        "Engine manifest",
        "Volumes",
        "Frames",
        "Quicklooks",
        "Missing quicklooks",
        "Semantic objects",
        "manual selection required / not loaded",
    ]:
        assert text in html
    for helper in ["renderBundleReadiness", "readinessValue"]:
        assert helper in html


def test_ppi_bundle_viewer_v06_demo_screenshot_mode_toggle():
    html = VIEWER.read_text(encoding="utf-8")

    assert 'id="demoScreenshotMode"' in html
    assert "Demo screenshot mode" in html
    assert "body.demo-screenshot-mode" in html
    assert "SCREENSHOT MODE · center viewport prioritized" in html
    for helper in ["toggleDemoScreenshotMode", "setDemoScreenshotMode"]:
        assert helper in html


def test_ppi_bundle_viewer_uses_dom_apis_for_untrusted_quicklook_paths():
    html = VIEWER.read_text(encoding="utf-8")

    assert "function renderFrameImage" in html
    assert "document.createElement('img')" in html
    assert "img.src = path" in html
    assert "img.alt =" in html
    assert 'frame.innerHTML = `<img src="${path}"' not in html
    assert "onerror=\"this.replaceWith" not in html


def test_ppi_bundle_viewer_v06_loads_manual_semantic_objects_honestly():
    html = VIEWER.read_text(encoding="utf-8")

    for element_id in ["semanticObjectsPanel", "semanticObjectsStatus", "semanticObjectsList"]:
        assert f'id="{element_id}"' in html
    for text in [
        "semantic_objects.json",
        "stormdeck.semantic_objects.v0",
        "semantic objects not loaded",
        "Semantic storm objects",
        "manual/sample annotation",
        "confidence",
        "object type",
        "interpretation limit",
        "sample velocity couplet",
        "manually annotated; not algorithmic detection",
        "manual/sample/inferred annotations are not observed radar data",
    ]:
        assert text in html
    for helper in ["loadSemanticObjects", "renderSemanticObjectsPanel", "semanticObjectRows"]:
        assert helper in html
