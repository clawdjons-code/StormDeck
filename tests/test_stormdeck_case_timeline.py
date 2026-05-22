import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "stormdeck_case_timeline.py"


def load_module():
    spec = importlib.util.spec_from_file_location("stormdeck_case_timeline", MODULE_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def sample_inventory():
    return {
        "root": "/home/atd_test/storm-deck-data/20260402_031550/CFILE/cfradial",
        "file_count_sampled": 6,
        "files": [
            {
                "file": "/case/KATD_Base_Data_20260402_010658_488217400.nc",
                "size_mb": 8.73,
                "instrument_name": "KATD",
                "site_name": "KATD",
                "scan_name": "QLCS_LDR_0.5Only",
                "start_time": "2026-04-02 01:06:58.488",
                "end_time": "2026-04-02 01:07:03.689",
                "sweep_count": 1,
                "sweeps": [{"name": "sweep_0", "dims": {"time": 113, "range": 1511, "prt": 3}, "sweep_mode": "sector", "sweep_fixed_angle": 0.5000014901161194}],
            },
            {
                "file": "/case/KATD_Base_Data_20260402_010703_774319400.nc",
                "size_mb": 105.56,
                "instrument_name": "KATD",
                "site_name": "KATD",
                "scan_name": "Supercell_Fast_Deg_Staggered_Test",
                "start_time": "2026-04-02 01:07:03.774",
                "end_time": "2026-04-02 01:08:45.096",
                "sweep_count": 20,
                "sweeps": [
                    {"name": "sweep_0", "dims": {"time": 113, "range": 1613, "prt": 3}, "sweep_mode": "sector", "sweep_fixed_angle": 0.5000014901161194},
                    {"name": "sweep_1", "dims": {"time": 113, "range": 1553, "prt": 3}, "sweep_mode": "sector", "sweep_fixed_angle": 0.899997889995575},
                    {"name": "sweep_2", "dims": {"time": 113, "range": 1523, "prt": 3}, "sweep_mode": "sector", "sweep_fixed_angle": 1.3000011444091797},
                ],
            },
            {
                "file": "/case/KATD_Base_Data_20260402_010845_115857400.nc",
                "size_mb": 11.98,
                "instrument_name": "KATD",
                "site_name": "KATD",
                "scan_name": "RHI_LDR_Narrow_Sector",
                "start_time": "2026-04-02 01:08:45.115",
                "end_time": "2026-04-02 01:08:52.295",
                "sweep_count": 9,
                "sweeps": [{"name": "sweep_0", "dims": {"time": 40, "range": 630, "prt": 3}, "sweep_mode": "rhi", "sweep_fixed_angle": 0.5000014901161194}],
            },
            {
                "file": "/case/KATD_Base_Data_20260402_010852_340975400.nc",
                "size_mb": 8.73,
                "instrument_name": "KATD",
                "site_name": "KATD",
                "scan_name": "QLCS_LDR_0.5Only",
                "start_time": "2026-04-02 01:08:52.340",
                "end_time": "2026-04-02 01:08:57.542",
                "sweep_count": 1,
                "sweeps": [{"name": "sweep_0", "dims": {"time": 113, "range": 1511, "prt": 3}, "sweep_mode": "sector", "sweep_fixed_angle": 0.5000014901161194}],
            },
            {
                "file": "/case/KATD_Base_Data_20260402_010857_627077400.nc",
                "size_mb": 105.56,
                "instrument_name": "KATD",
                "site_name": "KATD",
                "scan_name": "Supercell_Fast_Deg_Staggered_Test",
                "start_time": "2026-04-02 01:08:57.627",
                "end_time": "2026-04-02 01:10:40.043",
                "sweep_count": 20,
                "sweeps": [{"name": "sweep_0", "dims": {"time": 113, "range": 1613, "prt": 3}, "sweep_mode": "sector", "sweep_fixed_angle": 0.5000014901161194}],
            },
            {
                "file": "/case/KATD_Base_Data_20260402_011040_062875400.nc",
                "size_mb": 11.98,
                "instrument_name": "KATD",
                "site_name": "KATD",
                "scan_name": "RHI_LDR_Narrow_Sector",
                "start_time": "2026-04-02 01:10:40.062",
                "end_time": "2026-04-02 01:10:47.242",
                "sweep_count": 9,
                "sweeps": [{"name": "sweep_0", "dims": {"time": 40, "range": 630, "prt": 3}, "sweep_mode": "rhi", "sweep_fixed_angle": 0.5000014901161194}],
            },
        ],
    }


def test_builds_mixed_scan_case_timeline_from_inventory():
    mod = load_module()

    timeline = mod.build_case_timeline(sample_inventory(), case_id="20260402_031550_supercell")

    assert timeline["schema"] == "stormdeck.case_timeline.v0"
    assert timeline["case_id"] == "20260402_031550_supercell"
    assert timeline["volume_count"] == 6
    assert timeline["case_start_time"] == "2026-04-02 01:06:58.488"
    assert timeline["case_end_time"] == "2026-04-02 01:10:47.242"
    assert timeline["scan_name_counts"] == {
        "QLCS_LDR_0.5Only": 2,
        "RHI_LDR_Narrow_Sector": 2,
        "Supercell_Fast_Deg_Staggered_Test": 2,
    }
    assert timeline["scan_mode_counts"] == {"sector": 4, "rhi": 2}
    assert timeline["playlist_pattern_sample"] == ["QLCS_LDR_0.5Only", "Supercell_Fast_Deg_Staggered_Test", "RHI_LDR_Narrow_Sector"]
    assert timeline["warnings"][0].startswith("Mixed PPI/sector and RHI")


def test_preserves_per_scan_cadence_and_variable_gate_counts():
    mod = load_module()

    timeline = mod.build_case_timeline(sample_inventory(), case_id="case")

    supercell = timeline["scan_summaries"]["Supercell_Fast_Deg_Staggered_Test"]
    assert supercell["count"] == 2
    assert supercell["sweep_count_values"] == [20]
    assert supercell["median_start_spacing_s"] == 113.853
    assert supercell["gate_count_values_sample"] == [1613, 1553, 1523]
    assert timeline["engine_hints"]["contains_mixed_scan_strategies"] is True
    assert timeline["engine_hints"]["timeline_should_group_by_scan_name"] is True


def test_main_creates_missing_output_parent_directories(tmp_path):
    mod = load_module()
    inventory_path = tmp_path / "inventory.json"
    inventory_path.write_text(json.dumps(sample_inventory()), encoding="utf-8")
    output_path = tmp_path / "missing" / "nested" / "case_timeline.json"

    rc = mod.main([
        "--inventory", str(inventory_path),
        "--case-id", "case",
        "--out", str(output_path),
    ])

    assert rc == 0
    assert output_path.exists()
    timeline = json.loads(output_path.read_text(encoding="utf-8"))
    assert timeline["schema"] == "stormdeck.case_timeline.v0"
