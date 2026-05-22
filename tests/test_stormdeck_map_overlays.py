import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "stormdeck_map_overlays.py"


def load_module():
    spec = importlib.util.spec_from_file_location("stormdeck_map_overlays", MODULE_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def sample_config():
    return {
        "schema": "stormdeck.map_overlay_config.v0",
        "site": "KATD",
        "description": "Demo KATD map context.",
        "towns": [
            {"name": "Norman", "latitude_deg": 35.2226, "longitude_deg": -97.4395, "label_priority": 1},
            {"name": "Moore", "latitude_deg": 35.3395, "longitude_deg": -97.4867, "label_priority": 2},
        ],
        "warning_corridors": [
            {
                "id": "demo-warning-corridor",
                "label": "demo warning corridor",
                "source": "manual-demo",
                "active_product": False,
                "points": [
                    {"latitude_deg": 35.05, "longitude_deg": -98.05},
                    {"latitude_deg": 35.36, "longitude_deg": -98.02},
                    {"latitude_deg": 35.42, "longitude_deg": -97.55},
                    {"latitude_deg": 35.10, "longitude_deg": -97.58},
                ],
            }
        ],
        "boundary_sources": {"county_geojson": None, "state_geojson": None},
    }


def test_builds_map_overlays_from_config_without_boundary_sources():
    mod = load_module()

    overlays = mod.build_map_overlays(sample_config())

    assert overlays["schema"] == "stormdeck.map_overlays.v0"
    assert overlays["description"].startswith("Generated context overlays")
    assert overlays["source"]["kind"] == "manual-demo"
    assert overlays["source"]["site"] == "KATD"
    assert overlays["source"]["active_warning_product"] is False
    assert overlays["town_points"] == sample_config()["towns"]
    assert overlays["warning_corridors"][0]["id"] == "demo-warning-corridor"
    assert overlays["warning_corridors"][0]["active_product"] is False
    assert overlays["warning_corridors"][0]["confidence"] == "schematic context"
    assert overlays["county_boundaries"] == []
    assert overlays["state_boundaries"] == []


def test_main_writes_map_overlays_and_creates_parent_dirs(tmp_path):
    mod = load_module()
    config_path = tmp_path / "map_overlay_config.json"
    output_path = tmp_path / "missing" / "nested" / "map_overlays.json"
    config_path.write_text(json.dumps(sample_config()), encoding="utf-8")

    rc = mod.main(["--config", str(config_path), "--out", str(output_path)])

    assert rc == 0
    assert output_path.exists()
    overlays = json.loads(output_path.read_text(encoding="utf-8"))
    assert overlays["schema"] == "stormdeck.map_overlays.v0"
    assert len(overlays["town_points"]) == 2
    assert len(overlays["warning_corridors"]) == 1


def test_rejects_unknown_config_schema():
    mod = load_module()
    bad_config = sample_config() | {"schema": "stormdeck.map_overlays.v0"}

    try:
        mod.build_map_overlays(bad_config)
    except ValueError as error:
        assert "stormdeck.map_overlay_config.v0" in str(error)
    else:
        raise AssertionError("expected build_map_overlays to reject the wrong schema")
