import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SCRIPT = SCRIPTS / "stormdeck_vertical_slice.py"


def load_module():
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location("stormdeck_vertical_slice", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_builds_observed_native_rhi_vertical_slice_contract():
    mod = load_module()
    payload = mod.build_vertical_slice_from_arrays(
        field=[[1.0, -999.0, 30.0], [2.0, 8.0, 45.0], [3.0, 12.0, 50.0]],
        range_m=[1000, 2000, 3000],
        azimuth_deg=[200.0, 200.1, 200.0],
        elevation_deg=[0.5, 4.0, 8.0],
        field_name="REF",
        field_units="dBZ",
        source_path="sample.nc",
        sweep_name="sweep_0",
        scan_name="RHI demo",
    )

    assert payload["schema"] == "stormdeck.vertical_slice.v0"
    assert payload["scientific_status"] == "observed_native_rhi_gates_not_gridded_not_interpolated"
    assert payload["sweep"]["scan_type"] == "RHI"
    assert payload["values"][0][1] is None
    assert payload["viewer_hints"]["default_view"] == "native_rhi_vertical_slice"
    assert "not arbitrary A-B interpolation" in payload["warnings"][0]


def test_rejects_ppi_geometry_for_vertical_slice():
    mod = load_module()
    with pytest.raises(ValueError, match="native RHI-like geometry"):
        mod.build_vertical_slice_from_arrays(
            field=[[1.0, 2.0], [3.0, 4.0]],
            range_m=[1000, 2000],
            azimuth_deg=[180.0, 260.0],
            elevation_deg=[0.5, 0.6],
            field_name="REF",
            source_path="ppi.nc",
            sweep_name="sweep_0",
        )


def test_builds_vertical_slice_playlist_contract():
    mod = load_module()
    first = mod.build_vertical_slice_from_arrays(
        field=[[1.0, 2.0], [3.0, 4.0]],
        range_m=[1000, 2000],
        azimuth_deg=[200.0, 200.0],
        elevation_deg=[0.5, 5.0],
        field_name="REF",
        source_path="a.nc",
        source_time="2026-01-01T00:00:00Z",
        sweep_name="sweep_0",
    )
    second = mod.build_vertical_slice_from_arrays(
        field=[[2.0, 3.0], [4.0, 5.0]],
        range_m=[1000, 2000],
        azimuth_deg=[200.0, 200.0],
        elevation_deg=[0.5, 5.0],
        field_name="REF",
        source_path="b.nc",
        source_time="2026-01-01T00:01:00Z",
        sweep_name="sweep_0",
    )

    playlist = mod.build_vertical_slice_playlist([first, second], case_id="case", field="REF", strict_compatible=True)

    assert playlist["schema"] == "stormdeck.vertical_slice_playlist.v0"
    assert playlist["frame_count"] == 2
    assert playlist["frames"][1]["previous_frame_index"] == 0
    assert playlist["compatibility"]["status"] == "homogeneous_comparable"
    assert "no arbitrary A-B interpolation" in playlist["compatibility"]["operator_note"]


def test_strict_playlist_rejects_mixed_fixed_azimuths():
    mod = load_module()
    first = mod.build_vertical_slice_from_arrays(
        field=[[1.0], [2.0]], range_m=[1000], azimuth_deg=[200.0, 200.0], elevation_deg=[0.5, 5.0], field_name="REF", source_path="a.nc", sweep_name="sweep_0"
    )
    second = mod.build_vertical_slice_from_arrays(
        field=[[1.0], [2.0]], range_m=[1000], azimuth_deg=[210.0, 210.0], elevation_deg=[0.5, 5.0], field_name="REF", source_path="b.nc", sweep_name="sweep_0"
    )

    with pytest.raises(ValueError, match="Mixed fixed azimuths"):
        mod.build_vertical_slice_playlist([first, second], strict_compatible=True)
