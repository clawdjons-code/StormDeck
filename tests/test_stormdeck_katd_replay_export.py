import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "stormdeck_katd_replay_export.py"


def load_module():
    spec = importlib.util.spec_from_file_location("stormdeck_katd_replay_export", MODULE_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_case_id_from_katd_base_data_filename():
    mod = load_module()

    assert (
        mod.case_id_from_path(Path("/home/atd_test/storm-deck-data/KATD_Base_Data_20260123_205908_830894500.nc"))
        == "KATD_20260123_205908"
    )


def test_logical_artifact_layout_uses_expected_contract_names(tmp_path):
    mod = load_module()

    layout = mod.artifact_layout(tmp_path, "KATD_20260123_205908", "frame_000000")

    assert layout["case_manifest"].name == "case_manifest.json"
    assert layout["case_provenance"].name == "provenance.json"
    assert layout["frame_manifest"].as_posix().endswith("frames/frame_000000/frame_manifest.json")
    assert layout["geometry_summary"].name == "geometry_summary.json"
    assert layout["field_stats"].name == "field_stats.json"
    assert layout["qc_flags_summary"].name == "qc_flags_summary.json"
    assert layout["preview_dir"].as_posix().endswith("frames/frame_000000/previews")


def test_qc_flag_summary_preserves_flag_meanings_and_counts():
    mod = load_module()

    class FakeVar:
        shape = (2, 3)
        dtype = "uint8"
        flag_values = [0, 1]
        flag_meanings = "no_clutter clutter_identified"
        _FillValue = 255

        def __getitem__(self, key):
            import numpy as np

            return np.array([[0, 1, 0], [255, 1, 0]], dtype="uint8")

    summary = mod.summarize_qc_flag_var("CLTR", FakeVar())

    assert summary["present"] is True
    assert summary["shape"] == [2, 3]
    assert summary["nonzero_count"] == 2
    assert summary["valid_gate_count"] == 5
    assert summary["fill_value"] == 255
    assert summary["flag_meanings"] == "no_clutter clutter_identified"


def test_field_stats_include_required_percentiles_and_mask_minus_999():
    mod = load_module()

    class FakeVar:
        name = "REF"
        shape = (1, 4)
        dtype = "float32"
        units = "dBZ"
        long_name = "radar_equivalent_reflectivity_factor"
        _FillValue = -9999.0

        def __getitem__(self, key):
            import numpy as np

            return np.array([[10.0, 20.0, -999.0, -9999.0]], dtype="float32")

    summary = mod.summarize_field_var("REF", FakeVar())

    assert summary["present"] is True
    assert summary["shape"] == [1, 4]
    assert summary["valid_gate_count"] == 2
    assert summary["missing_gate_count"] == 2
    assert summary["p05"] is not None
    assert summary["p95"] is not None
