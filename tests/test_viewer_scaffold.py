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
    assert "FileReader" in html
    assert "renderCaseSummary" in html
    assert "renderTrackList" in html
    assert "renderChangePanel" in html
