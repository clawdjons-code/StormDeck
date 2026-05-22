import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "stormdeck_temporal_tracks.py"


def load_module():
    spec = importlib.util.spec_from_file_location("stormdeck_temporal_tracks", MODULE_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def sweep(name, mode, angle, time=10, range_=100):
    return {
        "name": name,
        "sweep_mode": mode,
        "sweep_fixed_angle": angle,
        "dims": {"time": time, "range": range_, "prt": 3},
        "variables": ["REF", "VEL", "ZDR"],
    }


def note_sweep():
    return {"note": "extra group omitted from abbreviated paste-back"}


def sample_inventory():
    return {
        "root": "/case/cfradial",
        "files": [
            {
                "file": "/case/qlcs-1.nc",
                "scan_name": "QLCS_LDR_0.5Only",
                "start_time": "2026-04-02 01:00:00.000",
                "end_time": "2026-04-02 01:00:05.200",
                "size_mb": 8.73,
                "sweep_count": 1,
                "sweeps": [sweep("sweep_0", "sector", 0.500001, time=113, range_=1511)],
            },
            {
                "file": "/case/supercell-full-1.nc",
                "scan_name": "Supercell_Fast_Deg_Staggered_Test",
                "start_time": "2026-04-02 01:00:05.300",
                "end_time": "2026-04-02 01:01:47.700",
                "size_mb": 105.56,
                "sweep_count": 20,
                "sweeps": [
                    sweep("sweep_0", "sector", 0.500001, time=113, range_=1613),
                    sweep("sweep_1", "sector", 0.899998, time=113, range_=1553),
                    sweep("sweep_2", "sector", 1.300001, time=113, range_=1523),
                    note_sweep(),
                ],
            },
            {
                "file": "/case/rhi-full-1.nc",
                "scan_name": "RHI_LDR_Narrow_Sector",
                "start_time": "2026-04-02 01:01:47.720",
                "end_time": "2026-04-02 01:01:54.900",
                "size_mb": 11.98,
                "sweep_count": 9,
                "sweeps": [
                    sweep("sweep_0", "rhi", 0.500001, time=40, range_=630),
                    sweep("sweep_1", "rhi", 0.500001, time=40, range_=630),
                    sweep("sweep_2", "rhi", 0.500001, time=40, range_=630),
                    note_sweep(),
                ],
            },
            {
                "file": "/case/supercell-fragment.nc",
                "scan_name": "Supercell_Fast_Deg_Staggered_Test",
                "start_time": "2026-04-02 01:01:54.920",
                "end_time": "2026-04-02 01:01:55.050",
                "size_mb": 0.29,
                "sweep_count": 1,
                "sweeps": [sweep("sweep_0", "sector", 18.899999, time=13, range_=310)],
            },
            {
                "file": "/case/rhi-fragment.nc",
                "scan_name": "RHI_LDR_Narrow_Sector",
                "start_time": "2026-04-02 01:01:55.070",
                "end_time": "2026-04-02 01:01:55.070",
                "size_mb": 0.12,
                "sweep_count": 1,
                "sweeps": [sweep("sweep_0", "rhi", 0.500001, time=1, range_=630)],
            },
            {
                "file": "/case/rhi-mixed-fragment.nc",
                "scan_name": "RHI_LDR_Narrow_Sector",
                "start_time": "2026-04-02 01:01:55.090",
                "end_time": "2026-04-02 01:01:55.070",
                "size_mb": 0.18,
                "sweep_count": 2,
                "sweeps": [
                    sweep("sweep_0", "rhi", 0.500001, time=1, range_=630),
                    sweep("sweep_1", "sector", 18.899999, time=1, range_=310),
                ],
            },
            {
                "file": "/case/qlcs-2.nc",
                "scan_name": "QLCS_LDR_0.5Only",
                "start_time": "2026-04-02 01:01:55.200",
                "end_time": "2026-04-02 01:02:00.400",
                "size_mb": 8.73,
                "sweep_count": 1,
                "sweeps": [sweep("sweep_0", "sector", 0.500001, time=113, range_=1511)],
            },
            {
                "file": "/case/supercell-full-2.nc",
                "scan_name": "Supercell_Fast_Deg_Staggered_Test",
                "start_time": "2026-04-02 01:02:00.500",
                "end_time": "2026-04-02 01:03:42.900",
                "size_mb": 105.56,
                "sweep_count": 20,
                "sweeps": [
                    sweep("sweep_0", "sector", 0.500001, time=113, range_=1613),
                    sweep("sweep_1", "sector", 0.899998, time=113, range_=1553),
                    sweep("sweep_2", "sector", 1.300001, time=113, range_=1523),
                    note_sweep(),
                ],
            },
        ],
    }


def test_builds_complete_tracks_and_quarantines_fragments():
    mod = load_module()

    tracks = mod.build_temporal_tracks(sample_inventory(), case_id="case")

    assert tracks["schema"] == "stormdeck.temporal_tracks.v0"
    assert tracks["case_id"] == "case"
    assert tracks["volume_counts"] == {
        "total": 8,
        "complete": 5,
        "quarantined": 3,
    }
    assert tracks["classification_counts"] == {
        "complete_low_level_sector": 2,
        "complete_native_rhi": 1,
        "complete_supercell_3d": 2,
        "fragment_or_transition": 3,
    }
    assert len(tracks["quarantine"]) == 3
    assert {q["reason"] for q in tracks["quarantine"]} == {
        "size_below_1mb;sweep_count_1_expected_20",
        "size_below_1mb;sweep_count_1_expected_9",
        "size_below_1mb;sweep_count_2_expected_9;mixed_scan_modes",
    }

    track_ids = {t["track_id"]: t for t in tracks["tracks"]}
    assert "QLCS_LDR_0.5Only__sector__0.5deg__complete" in track_ids
    assert "Supercell_Fast_Deg_Staggered_Test__sector__0.5deg__complete" in track_ids
    assert "Supercell_Fast_Deg_Staggered_Test__sector__0.9deg__complete" in track_ids
    assert "RHI_LDR_Narrow_Sector__native_rhi__complete" in track_ids
    assert track_ids["Supercell_Fast_Deg_Staggered_Test__sector__0.5deg__complete"]["volume_count"] == 2
    assert track_ids["Supercell_Fast_Deg_Staggered_Test__sector__0.5deg__complete"]["median_spacing_s"] == 115.2
    assert track_ids["RHI_LDR_Narrow_Sector__native_rhi__complete"]["native_rhi"] is True


def test_cli_writes_temporal_tracks_to_missing_output_directory(tmp_path):
    mod = load_module()
    inventory_path = tmp_path / "inventory.json"
    inventory_path.write_text(json.dumps(sample_inventory()), encoding="utf-8")
    output_path = tmp_path / "exports" / "tracks" / "temporal_tracks.json"

    rc = mod.main([
        "--inventory", str(inventory_path),
        "--case-id", "case",
        "--out", str(output_path),
    ])

    assert rc == 0
    assert output_path.exists()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["schema"] == "stormdeck.temporal_tracks.v0"
