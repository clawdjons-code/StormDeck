import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "stormdeck_change_summary.py"


def load_module():
    spec = importlib.util.spec_from_file_location("stormdeck_change_summary", MODULE_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def volume(ordinal, start, end, file_name):
    return {
        "ordinal": ordinal,
        "file": f"/case/{file_name}",
        "start_time": start,
        "end_time": end,
        "duration_s": 5.0,
    }


def sample_temporal_tracks():
    return {
        "schema": "stormdeck.temporal_tracks.v0",
        "case_id": "case",
        "source_root": "/case/cfradial",
        "volume_counts": {"total": 8, "complete": 5, "quarantined": 3},
        "classification_counts": {
            "complete_low_level_sector": 2,
            "complete_native_rhi": 1,
            "complete_supercell_3d": 2,
            "fragment_or_transition": 3,
        },
        "pairing_rules": {
            "match_track_id": True,
            "match_scan_name": True,
            "match_scan_mode": True,
            "match_fixed_angle_deg_tolerance": 0.05,
            "exclude_quarantined": True,
        },
        "tracks": [
            {
                "track_id": "QLCS_LDR_0.5Only__sector__0.5deg__complete",
                "scan_name": "QLCS_LDR_0.5Only",
                "scan_mode": "sector",
                "track_kind": "fixed_angle_sweep",
                "fixed_angle_deg": 0.5,
                "native_rhi": False,
                "volume_count": 2,
                "case_start_time": "2026-04-02 01:00:00.000",
                "case_end_time": "2026-04-02 01:01:55.400",
                "median_spacing_s": 115.2,
                "volumes": [
                    volume(0, "2026-04-02 01:00:00.000", "2026-04-02 01:00:05.200", "qlcs-1.nc"),
                    volume(6, "2026-04-02 01:01:55.200", "2026-04-02 01:02:00.400", "qlcs-2.nc"),
                ],
            },
            {
                "track_id": "Supercell_Fast_Deg_Staggered_Test__sector__0.5deg__complete",
                "scan_name": "Supercell_Fast_Deg_Staggered_Test",
                "scan_mode": "sector",
                "track_kind": "fixed_angle_sweep",
                "fixed_angle_deg": 0.5,
                "native_rhi": False,
                "volume_count": 2,
                "case_start_time": "2026-04-02 01:00:05.300",
                "case_end_time": "2026-04-02 01:03:42.900",
                "median_spacing_s": 115.2,
                "volumes": [
                    volume(1, "2026-04-02 01:00:05.300", "2026-04-02 01:01:47.700", "supercell-full-1.nc"),
                    volume(7, "2026-04-02 01:02:00.500", "2026-04-02 01:03:42.900", "supercell-full-2.nc"),
                ],
            },
            {
                "track_id": "RHI_LDR_Narrow_Sector__native_rhi__complete",
                "scan_name": "RHI_LDR_Narrow_Sector",
                "scan_mode": "rhi",
                "track_kind": "native_rhi",
                "fixed_angle_deg": None,
                "native_rhi": True,
                "volume_count": 1,
                "case_start_time": "2026-04-02 01:01:47.720",
                "case_end_time": "2026-04-02 01:01:54.900",
                "median_spacing_s": None,
                "volumes": [volume(2, "2026-04-02 01:01:47.720", "2026-04-02 01:01:54.900", "rhi-full-1.nc")],
            },
        ],
        "quarantine": [
            {
                "ordinal": 3,
                "file": "/case/supercell-fragment.nc",
                "scan_name": "Supercell_Fast_Deg_Staggered_Test",
                "start_time": "2026-04-02 01:01:54.920",
                "end_time": "2026-04-02 01:01:55.050",
                "size_mb": 0.29,
                "sweep_count": 1,
                "scan_modes": ["sector"],
                "classification": "fragment_or_transition",
                "reason": "size_below_1mb;sweep_count_1_expected_20",
            },
            {
                "ordinal": 4,
                "file": "/case/rhi-fragment.nc",
                "scan_name": "RHI_LDR_Narrow_Sector",
                "start_time": "2026-04-02 01:01:55.070",
                "end_time": "2026-04-02 01:01:55.070",
                "size_mb": 0.12,
                "sweep_count": 1,
                "scan_modes": ["rhi"],
                "classification": "fragment_or_transition",
                "reason": "size_below_1mb;sweep_count_1_expected_9",
            },
            {
                "ordinal": 5,
                "file": "/case/rhi-mixed-fragment.nc",
                "scan_name": "RHI_LDR_Narrow_Sector",
                "start_time": "2026-04-02 01:01:55.090",
                "end_time": "2026-04-02 01:01:55.070",
                "size_mb": 0.18,
                "sweep_count": 2,
                "scan_modes": ["rhi", "sector"],
                "classification": "fragment_or_transition",
                "reason": "size_below_1mb;sweep_count_2_expected_9;mixed_scan_modes",
            },
        ],
    }


def test_builds_metadata_safe_change_summary_for_each_track():
    mod = load_module()

    summary = mod.build_change_summary(sample_temporal_tracks())

    assert summary["schema"] == "stormdeck.change_summary.v0"
    assert summary["case_id"] == "case"
    assert summary["source_schema"] == "stormdeck.temporal_tracks.v0"
    assert summary["summary_counts"] == {
        "tracks_total": 3,
        "track_comparisons": 2,
        "tracks_without_comparison": 1,
        "quarantine_events": 3,
    }
    assert summary["engine_hints"]["field_value_deltas_included"] is False
    assert summary["engine_hints"]["compare_only_within_track"] is True

    qlcs = next(c for c in summary["track_changes"] if c["track_id"] == "QLCS_LDR_0.5Only__sector__0.5deg__complete")
    assert qlcs["comparison_available"] is True
    assert qlcs["from_ordinal"] == 0
    assert qlcs["to_ordinal"] == 6
    assert qlcs["elapsed_s"] == 115.2
    assert qlcs["cadence_status"] == "on_cadence"
    assert qlcs["quarantine_events_between"] == 3
    assert qlcs["operator_message"] == "Metadata-safe comparison only; radar field deltas not computed."

    rhi = next(c for c in summary["track_changes"] if c["track_id"] == "RHI_LDR_Narrow_Sector__native_rhi__complete")
    assert rhi["comparison_available"] is False
    assert rhi["reason"] == "fewer_than_2_complete_volumes"


def test_cli_writes_summary_to_missing_output_directory(tmp_path):
    mod = load_module()
    tracks_path = tmp_path / "temporal_tracks.json"
    tracks_path.write_text(json.dumps(sample_temporal_tracks()), encoding="utf-8")
    output_path = tmp_path / "exports" / "change_summary.json"

    rc = mod.main([
        "--temporal-tracks", str(tracks_path),
        "--out", str(output_path),
    ])

    assert rc == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["schema"] == "stormdeck.change_summary.v0"
