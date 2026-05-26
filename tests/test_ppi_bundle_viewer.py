from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VIEWER = ROOT / "viewer" / "ppi_bundle_viewer.html"


def test_ppi_bundle_viewer_exists_and_targets_replay_index():
    html = VIEWER.read_text(encoding="utf-8")

    assert "StormDeck PPI Replay Bundle Viewer" in html
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
        "not temporal storm evidence",
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
