import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "stormdeck_volume_index.py"


def load_module():
    spec = importlib.util.spec_from_file_location("stormdeck_volume_index", MODULE_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def sample_manifest():
    return {
        "stormdeck_schema": "stormdeck.case_probe.v0",
        "source_nc": "/home/atd_test/storm-deck-data/KATD_Base_Data_20260522_123630_436049100.nc",
        "radar_id": "KATD",
        "site_name": "KATD",
        "scan_name": "Base Data",
        "start_time": "2026-05-22T12:36:30Z",
        "end_time": "2026-05-22T12:38:10Z",
        "duration_s_from_offsets": 100.1230251789093,
        "sweep_count": 2,
        "volume_type": "PPI_SECTOR_VOLUME",
        "scientific_status": "observed_native_radar_data_quicklook_not_gridded_not_interpolated",
        "sweeps": [
            {
                "sweep_name": "sweep_0",
                "scan_type": "PPI_SECTOR",
                "fixed_angle_type": "elevation",
                "fixed_angle_deg": 0.5000014901161194,
                "ray_count": 1963,
                "gate_count": 1500,
                "range": {"first_gate_m": 648.281, "last_gate_m": 299000.0, "gate_spacing_m_approx": 224.844, "shared_axis": True},
                "time": {"start_offset_s": 0.0, "end_offset_s": 8.0, "duration_s": 8.0},
                "fields": {
                    "REF": {"present": True, "source_variable": "REF", "valid_gate_count": 42, "missing_gate_count": 3, "min": -5.0, "max": 61.0, "p50": 17.0},
                    "VEL": {"present": False},
                },
                "renders": [{"png": "/tmp/export/quicklooks/sweep_0_REF.png", "render_type": "native_sector_ppi_observed_gates"}],
            },
            {
                "sweep_name": "sweep_1",
                "scan_type": "PPI_SECTOR",
                "fixed_angle_type": "elevation",
                "fixed_angle_deg": 19.500003814697266,
                "ray_count": 310,
                "gate_count": 1500,
                "range": {"first_gate_m": 648.281, "last_gate_m": 299000.0, "gate_spacing_m_approx": 224.844, "shared_axis": True},
                "time": {"start_offset_s": 92.0, "end_offset_s": 100.1230251789093, "duration_s": 8.1230251789093},
                "fields": {"REF": {"present": True, "source_variable": "REF", "valid_gate_count": 7, "missing_gate_count": 1, "min": -1.0, "max": 49.0}},
                "renders": [{"png": "/tmp/export/quicklooks/sweep_1_REF.png", "render_type": "native_sector_ppi_observed_gates"}],
            },
        ],
    }


def test_builds_engine_facing_volume_index_with_relative_quicklook_paths():
    mod = load_module()

    index = mod.build_volume_index(sample_manifest(), manifest_path=Path("/tmp/export/manifest.json"))

    assert index["schema"] == "stormdeck.volume_index.v0"
    assert index["source"]["file"] == "/home/atd_test/storm-deck-data/KATD_Base_Data_20260522_123630_436049100.nc"
    assert index["volume"]["type"] == "PPI_SECTOR_VOLUME"
    assert index["volume"]["sweep_count"] == 2
    assert index["volume"]["duration_s"] == 100.1230251789093
    assert index["volume"]["average_seconds_per_sweep"] == 50.06151258945465
    assert index["sweeps"][0]["fixed_angle_deg"] == 0.5000014901161194
    assert index["sweeps"][0]["fields"]["REF"]["quicklook_png"] == "quicklooks/sweep_0_REF.png"
    assert index["sweeps"][0]["fields"]["VEL"]["present"] is False
    assert index["client_contract"]["quicklooks_are_preview_only"] is True


def test_preserves_variable_ray_counts_for_adaptive_sector_volumes():
    mod = load_module()

    index = mod.build_volume_index(sample_manifest(), manifest_path=Path("/tmp/export/manifest.json"))

    assert [s["ray_count"] for s in index["sweeps"]] == [1963, 310]
    assert index["engine_hints"]["ray_counts_vary_by_sweep"] is True
    assert index["engine_hints"]["assume_uniform_ray_count"] is False
