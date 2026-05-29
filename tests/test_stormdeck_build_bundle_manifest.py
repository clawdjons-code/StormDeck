import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "stormdeck_build_bundle_manifest.py"


def load_module():
    spec = importlib.util.spec_from_file_location("stormdeck_build_bundle_manifest", SCRIPT)
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
        "scan_name": "ATD Demo TPRT",
        "start_time": "2026-05-22 12:36:30.436",
        "end_time": "2026-05-22 12:38:10.559",
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
        "purpose": "sample browser fixture",
        "volume_count": 1,
        "scan_mode": "sector",
        "scan_name": "ATD Demo TPRT",
        "warnings": ["not storm motion"],
        "volumes": [{"file": f"/data/{vol_id}.nc", "scan_name": "ATD Demo TPRT", "sweep_count": 1}],
    }
    (root / "ppi_tprt_replay_index.json").write_text(json.dumps(index))
    validation = {
        "schema": "stormdeck.replay_bundle_validation.v0",
        "status": "ready",
        "volume_count": 1,
        "quicklook_count": 3,
        "missing_quicklook_count": 0,
    }
    (root / "bundle_validation.json").write_text(json.dumps(validation))
    return root


def test_build_bundle_manifest_creates_godot_ready_playlist(tmp_path):
    mod = load_module()
    root = make_bundle(tmp_path)

    bundle = mod.build_bundle_manifest(root)

    assert bundle["schema"] == "stormdeck.bundle_manifest.v0"
    assert bundle["consumer_hints"]["godot_resource_loader"] == "json_plus_relative_png_paths"
    assert bundle["compatibility"]["temporal_comparison"] == "sample_browse_only"
    assert bundle["validation"]["status"] == "ready"
    assert bundle["fields"] == ["REF", "VEL", "SW"]
    assert bundle["sidecars"]["vertical_slice_playlist"]["path"] == "vertical_slice_playlist.json"
    assert bundle["sidecars"]["vertical_slice_playlist"]["exists"] is False
    assert len(bundle["frames"]) == 3
    first = bundle["frames"][0]
    assert first["volume_id"] == "KATD_Base_Data_20260522_123630_436049100"
    assert first["field"] == "REF"
    assert first["quicklook_path"] == "volumes/KATD_Base_Data_20260522_123630_436049100/quicklooks/sweep_0_REF.png"
    assert first["fixed_angle_display"] == "0.5° elevation"
    assert first["range_display"] == "441.1 km"
    assert first["provenance"] == "observed_native_quicklook_png"


def test_main_writes_bundle_manifest_json(tmp_path):
    mod = load_module()
    root = make_bundle(tmp_path)
    out = root / "stormdeck_bundle_manifest.json"

    code = mod.main([str(root), "--out", str(out)])

    assert code == 0
    written = json.loads(out.read_text())
    assert written["schema"] == "stormdeck.bundle_manifest.v0"
    assert written["frame_count"] == 3
