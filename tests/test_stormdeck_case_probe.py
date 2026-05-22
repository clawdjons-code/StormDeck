import importlib.util
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "stormdeck_case_probe.py"


def load_module():
    spec = importlib.util.spec_from_file_location("stormdeck_case_probe", MODULE_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_classifies_sector_ppi_from_coordinate_arrays():
    mod = load_module()

    summary = mod.classify_sweep_geometry(
        source_sweep_mode="sector",
        azimuth_deg=np.linspace(145.866, 235.334, 103),
        elevation_deg=np.full(103, 0.500001),
        top_fixed_angle=0.500001,
        group_fixed_angle=0.500001,
    )

    assert summary["scan_type"] == "PPI_SECTOR"
    assert summary["fixed_angle_type"] == "elevation"
    assert round(summary["fixed_angle_deg"], 6) == 0.500001
    assert summary["azimuth"]["varies"] is True
    assert summary["elevation"]["varies"] is False
    assert round(summary["azimuth"]["span_deg"], 3) == 89.468


def test_classifies_rhi_from_coordinate_arrays_not_group_fixed_angle():
    mod = load_module()

    summary = mod.classify_sweep_geometry(
        source_sweep_mode="rhi",
        azimuth_deg=np.full(20, 200.602096),
        elevation_deg=np.linspace(0.500001, 10.000002, 20),
        top_fixed_angle=200.602096,
        group_fixed_angle=0.500001,
    )

    assert summary["scan_type"] == "RHI"
    assert summary["fixed_angle_type"] == "azimuth"
    assert round(summary["fixed_angle_deg"], 6) == 200.602096
    assert summary["azimuth"]["varies"] is False
    assert summary["elevation"]["varies"] is True
    assert round(summary["elevation"]["span_deg"], 3) == 9.5
    assert summary["metadata_fixed_angles"]["group_sweep_fixed_angle"] == 0.500001


def test_range_summary_uses_actual_first_gate_and_spacing():
    mod = load_module()
    ranges = np.array([648.281005859375, 873.1253662109375, 1097.9697265625])

    summary = mod.summarize_range_axis(ranges)

    assert summary["first_gate_m"] == 648.281005859375
    assert summary["last_gate_m"] == 1097.9697265625
    assert round(summary["gate_spacing_m_approx"], 6) == round(224.8443603515625, 6)
    assert summary["shared_axis"] is True


def test_infers_volume_type_from_sweep_types():
    mod = load_module()

    assert mod.infer_volume_type(["PPI_SECTOR"] * 14) == "PPI_SECTOR_VOLUME"
    assert mod.infer_volume_type(["RHI"] * 11) == "RHI_SET"
    assert mod.infer_volume_type(["PPI_SECTOR", "RHI"]) == "MIXED_SCAN_SET"


def test_masks_atd_minus_999_moment_sentinel_values():
    mod = load_module()

    class FakeVar:
        def __getitem__(self, key):
            return np.array([[0.0, -999.0, 5.0]])

    arr = mod.read_masked_field(FakeVar())

    assert np.isfinite(arr[0, 0])
    assert np.isnan(arr[0, 1])
    assert np.isfinite(arr[0, 2])
