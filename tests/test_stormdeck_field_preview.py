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
    assert preview["viewer_hints"]["color_table"] == "atd_reflectivity_dbz"
    assert preview["display_metadata"]["scan_name"] is None
    assert preview["display_metadata"]["radial_count"] == 3
    assert preview["display_metadata"]["fixed_angle_label"] == "0.5°"
    assert preview["site"] == {
        "latitude_deg": None,
        "longitude_deg": None,
        "altitude_m": None,
        "source": "not_available",
    }
    assert preview["map_context"]["status"] == "not_georeferenced_no_site_location"
    assert preview["map_context"]["rendering_mode"] == "sector_outline_only_not_gridded"
    assert preview["warnings"] == [
        "Observed radar field sample only; not a gridded volume and not a field-value delta."
    ]


def test_includes_radar_site_and_projected_sector_context_when_available():
    mod = load_module()
    preview = mod.build_field_preview_from_arrays(
        field=np.ones((3, 4)),
        range_m=np.array([0.0, 1000.0, 2000.0, 3000.0]),
        azimuth_deg=np.array([210.0, 215.0, 220.0]),
        elevation_deg=np.array([0.5, 0.5, 0.5]),
        field_name="REF",
        source_path="sample.nc",
        sweep_name="sweep_0",
        radar_latitude_deg=35.333,
        radar_longitude_deg=-97.277,
        radar_altitude_m=365.0,
    )

    assert preview["site"] == {
        "latitude_deg": 35.333,
        "longitude_deg": -97.277,
        "altitude_m": 365.0,
        "source": "CfRadial site metadata",
    }
    assert preview["map_context"]["status"] == "georeferenced_sector_outline_available"
    assert preview["map_context"]["rendering_mode"] == "sector_outline_only_not_gridded"
    assert preview["map_context"]["sector_outline"]["azimuth_min_deg"] == 210.0
    assert preview["map_context"]["sector_outline"]["azimuth_max_deg"] == 220.0
    assert preview["map_context"]["sector_outline"]["range_max_m"] == 3000.0


def test_labels_ppi_elevation_to_tenth_degree_despite_float_jitter():
    mod = load_module()
    preview = mod.build_field_preview_from_arrays(
        field=np.ones((4, 3)),
        range_m=np.array([1000.0, 2000.0, 3000.0]),
        azimuth_deg=np.array([200.0, 201.0, 202.0, 203.0]),
        elevation_deg=np.array([0.49999997, 0.50000003, 0.59999996, 0.60000004]),
        field_name="REF",
        field_units="dBZ",
        source_path="sample.nc",
        sweep_name="sweep_0",
    )

    display = preview["display_metadata"]
    assert display["fixed_angle_label"] == "~0.6°"
    assert display["elevation_precision_deg"] == 0.1
    assert display["elevation_median_deg"] == 0.6
    assert display["elevation_min_deg"] == 0.5
    assert display["elevation_max_deg"] == 0.6


def test_builds_browser_safe_field_preview_playlist_contract():
    mod = load_module()
    first = mod.build_field_preview_from_arrays(
        field=np.array([[1.0, 2.0], [3.0, 4.0]]),
        range_m=np.array([1000.0, 2000.0]),
        azimuth_deg=np.array([180.0, 181.0]),
        elevation_deg=np.array([0.5, 0.5]),
        field_name="REF",
        field_units="dBZ",
        source_path="/case/frame_000.nc",
        sweep_name="sweep_0",
        source_time="2026-04-02T03:15:50Z",
    )
    second = mod.build_field_preview_from_arrays(
        field=np.array([[2.0, 4.0], [6.0, 8.0]]),
        range_m=np.array([1000.0, 2000.0]),
        azimuth_deg=np.array([182.0, 183.0]),
        elevation_deg=np.array([0.5, 0.5]),
        field_name="REF",
        field_units="dBZ",
        source_path="/case/frame_001.nc",
        sweep_name="sweep_0",
        source_time="2026-04-02T03:15:58Z",
    )

    playlist = mod.build_field_preview_playlist(
        [first, second],
        case_id="20260402_031550_supercell",
        field="REF",
    )

    assert playlist["schema"] == "stormdeck.field_preview_playlist.v0"
    assert playlist["case_id"] == "20260402_031550_supercell"
    assert playlist["field"] == "REF"
    assert playlist["frame_count"] == 2
    assert playlist["timeline"]["start_time"] == "2026-04-02T03:15:50Z"
    assert playlist["timeline"]["end_time"] == "2026-04-02T03:15:58Z"
    assert playlist["frames"][0]["frame_index"] == 0
    assert playlist["frames"][1]["frame_index"] == 1
    assert playlist["frames"][1]["previous_frame_index"] == 0
    assert playlist["frames"][1]["preview"]["values"] == [[2.0, 4.0], [6.0, 8.0]]
    assert "frame playlist" in playlist["warnings"][0]
    assert "not motion interpolation" in playlist["warnings"][0]


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
