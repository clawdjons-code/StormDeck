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
        "StormDeck bundle browser v0.4",
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
        "StormDeck bundle browser v0.4",
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
