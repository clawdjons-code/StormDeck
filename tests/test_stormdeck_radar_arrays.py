import importlib.util
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts" / "stormdeck_radar_arrays.py"
SCRIPT_DIR = ROOT / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


class FakeVar:
    name = "REF"
    shape = (1, 5)
    dtype = "float32"
    _FillValue = -9999.0

    def __init__(self, values):
        self.values = np.asarray(values, dtype="float32")

    def __getitem__(self, key):
        return self.values


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_shared_mask_helper_masks_katd_minus_999_and_fill_value():
    mod = load_module(HELPER, "stormdeck_radar_arrays")

    arr = mod.masked_numeric_array(FakeVar([[12.0, -998.0, -999.0, -9999.0, 42.0]]))

    assert np.isfinite(arr[0, 0])
    assert np.isfinite(arr[0, 1])  # do not over-mask valid odd-unit values above the sentinel
    assert np.isnan(arr[0, 2])
    assert np.isnan(arr[0, 3])
    assert arr[0, 4] == 42.0


def test_all_radar_renderers_use_shared_minus_999_masking_contract():
    modules = {
        "stormdeck_katd_replay_export": "masked_numeric_array",
        "stormdeck_field_preview": "read_masked_field",
        "stormdeck_case_probe": "read_masked_field",
        "stormdeck_3d_frame_render": "masked_data",
        "stormdeck_single_frame_preview": "masked_data",
    }
    for module_name, function_name in modules.items():
        mod = load_module(SCRIPT_DIR / f"{module_name}.py", module_name)
        fn = getattr(mod, function_name)
        if function_name == "masked_data":
            arr = fn(np, FakeVar([[1.0, -999.0, -9999.0, 5.0]]))
        else:
            arr = fn(FakeVar([[1.0, -999.0, -9999.0, 5.0]]))
        assert int(np.isfinite(arr).sum()) == 2, module_name
        assert int(np.isnan(arr).sum()) == 2, module_name


def test_no_script_keeps_divergent_minus_9990_sentinel_literal():
    offenders = []
    for path in SCRIPT_DIR.glob("*.py"):
        if path.name == "stormdeck_radar_arrays.py":
            continue
        text = path.read_text(encoding="utf-8")
        if "-9990" in text:
            offenders.append(path.name)
    assert offenders == []
