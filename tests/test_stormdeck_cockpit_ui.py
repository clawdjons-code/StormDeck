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
    ]:
        assert css_var in html

    for js_hook in [
        "applyAdaptiveLayout",
        "replayWidthSlider.addEventListener",
        "crossHeightSlider.addEventListener",
        "bottomCardSlider.addEventListener",
        "resetLayoutButton.addEventListener",
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
    ]:
        assert css_contract in html
