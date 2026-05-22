import importlib.util
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "stormdeck_field_preview.py"


def load_module():
    spec = importlib.util.spec_from_file_location("stormdeck_field_preview", MODULE_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_builds_browser_safe_observed_gate_preview_contract():
    mod = load_module()
    field = np.array([
        [5.0, 10.0, -999.0, 20.0],
        [15.0, 25.0, 35.0, 45.0],
        [np.nan, 30.0, 40.0, 50.0],
    ])
    preview = mod.build_field_preview_from_arrays(
        field=field,
        range_m=np.array([1000.0, 2000.0, 3000.0, 4000.0]),
        azimuth_deg=np.array([180.0, 181.0, 182.0]),
        elevation_deg=np.array([0.5, 0.5, 0.5]),
        field_name="DBZ",
        field_units="dBZ",
        source_path="/data/stormdeck/case/KATD.nc",
        sweep_name="sweep_0",
        max_rays=2,
        max_gates=3,
    )

    assert preview["schema"] == "stormdeck.field_preview.v0"
    assert preview["scientific_status"] == "observed_native_gates_not_gridded_not_interpolated"
    assert preview["source"]["path"] == "/data/stormdeck/case/KATD.nc"
    assert preview["sweep"]["name"] == "sweep_0"
    assert preview["field"]["name"] == "DBZ"
    assert preview["field"]["units"] == "dBZ"
    assert preview["field"]["stats"]["valid_gate_count"] == 10
    assert preview["sampling"]["ray_stride"] == 2
    assert preview["sampling"]["gate_stride"] == 2
    assert preview["sampling"]["sampled_ray_count"] == 2
    assert preview["sampling"]["sampled_gate_count"] == 2
    assert preview["coordinates"]["azimuth_deg"] == [180.0, 182.0]
    assert preview["coordinates"]["range_m"] == [1000.0, 3000.0]
    assert preview["values"] == [[5.0, None], [None, 40.0]]
    assert preview["viewer_hints"]["default_view"] == "native_polar_sweep"
    assert preview["warnings"] == [
        "Observed radar field sample only; not a gridded volume and not a field-value delta."
    ]


def test_rejects_mismatched_geometry_lengths():
    mod = load_module()

    try:
        mod.build_field_preview_from_arrays(
            field=np.ones((2, 3)),
            range_m=np.array([1000.0, 2000.0]),
            azimuth_deg=np.array([180.0, 181.0]),
            elevation_deg=np.array([0.5, 0.5]),
            field_name="DBZ",
            source_path="sample.nc",
            sweep_name="sweep_0",
        )
    except ValueError as exc:
        assert "range length" in str(exc)
    else:
        raise AssertionError("expected range length validation failure")
