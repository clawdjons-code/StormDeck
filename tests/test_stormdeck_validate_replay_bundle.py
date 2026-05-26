import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "stormdeck_validate_replay_bundle.py"


def load_module():
    spec = importlib.util.spec_from_file_location("stormdeck_validate_replay_bundle", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def make_bundle(tmp_path):
    root = tmp_path / "KATD_sample_inventory"
    vol_id = "KATD_Base_Data_20260522_123630_436049100"
    quicklooks = root / "volumes" / vol_id / "quicklooks"
    quicklooks.mkdir(parents=True)
    manifest = {
        "volume_type": "PPI_SECTOR_VOLUME",
        "sweeps": [
            {
                "sweep_name": "sweep_0",
                "fixed_angle_type": "elevation",
                "fixed_angle_deg": 0.5000014901161194,
                "ray_count": 103,
                "gate_count": 1963,
                "range": {"last_gate_m": 441145.0},
                "nyquist_velocity": {"median_mps": 49.73},
            }
        ],
    }
    (root / "volumes" / vol_id / "manifest.json").write_text(json.dumps(manifest))
    for field in ["REF", "VEL", "SW"]:
        (quicklooks / f"sweep_0_{field}.png").write_bytes(b"fake png placeholder")
    index = {
        "schema": "stormdeck.ppi_replay_index.v0",
        "case_id": "KATD_sample_inventory_ATD_Demo_TPRT_only",
        "volume_count": 1,
        "volumes": [{"file": f"/data/{vol_id}.nc", "scan_name": "ATD Demo TPRT", "sweep_count": 1}],
    }
    (root / "ppi_tprt_replay_index.json").write_text(json.dumps(index))
    return root


def test_validate_bundle_reports_ready_artifacts(tmp_path):
    mod = load_module()
    root = make_bundle(tmp_path)

    report = mod.validate_bundle(root)

    assert report["schema"] == "stormdeck.replay_bundle_validation.v0"
    assert report["status"] == "ready"
    assert report["volume_count"] == 1
    assert report["quicklook_count"] == 3
    assert report["missing_quicklook_count"] == 0
    assert report["volumes"][0]["status"] == "ready"
    assert report["volumes"][0]["sweeps"][0]["fixed_angle_display"] == "0.5° elevation"
    assert report["volumes"][0]["sweeps"][0]["range_display"] == "441.1 km"


def test_validate_bundle_flags_missing_pngs_without_failing(tmp_path):
    mod = load_module()
    root = make_bundle(tmp_path)
    (root / "volumes" / "KATD_Base_Data_20260522_123630_436049100" / "quicklooks" / "sweep_0_SW.png").unlink()

    report = mod.validate_bundle(root)

    assert report["status"] == "incomplete"
    assert report["missing_quicklook_count"] == 1
    assert "sweep_0_SW.png" in report["volumes"][0]["missing_quicklooks"]
