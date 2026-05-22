import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "stormdeck_case_manifest.py"


def load_module():
    spec = importlib.util.spec_from_file_location("stormdeck_case_manifest", MODULE_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, schema: str, **extra):
    payload = {"schema": schema, **extra}
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_builds_case_manifest_from_export_directory(tmp_path):
    mod = load_module()
    write_json(tmp_path / "case_timeline.json", "stormdeck.case_timeline.v0", case_id="case-a")
    write_json(tmp_path / "temporal_tracks.json", "stormdeck.temporal_tracks.v0", case_id="case-a")
    write_json(tmp_path / "change_summary.json", "stormdeck.change_summary.v0", case_id="case-a")
    write_json(tmp_path / "field_preview_playlist.json", "stormdeck.field_preview_playlist.v0", case_id="case-a", frame_count=12)
    write_json(tmp_path / "map_overlays.json", "stormdeck.map_overlays.v0", caveats=["context overlays only"])

    manifest = mod.build_case_manifest(
        export_dir=tmp_path,
        case_id="case-a",
        source_root="/home/atd_test/storm-deck-data/20260402_031550",
    )

    assert manifest["schema"] == "stormdeck.case_manifest.v0"
    assert manifest["case_id"] == "case-a"
    assert manifest["source_root"] == "/home/atd_test/storm-deck-data/20260402_031550"
    assert manifest["readiness"]["status"] == "ready"
    assert manifest["readiness"]["loaded_export_count"] == 5
    assert manifest["readiness"]["expected_export_count"] == 5
    assert manifest["readiness"]["loaded_required_count"] == 4
    assert manifest["readiness"]["required_count"] == 4
    assert manifest["artifacts"]["field_preview"]["filename"] == "field_preview_playlist.json"
    assert manifest["artifacts"]["field_preview"]["schema"] == "stormdeck.field_preview_playlist.v0"
    assert manifest["artifacts"]["case_timeline"]["required"] is True
    assert "Browser can fetch artifacts when served from the export directory" in manifest["viewer_hints"]["serving_note"]


def test_manifest_marks_missing_optional_map_overlays_but_missing_required_not_ready(tmp_path):
    mod = load_module()
    write_json(tmp_path / "case_timeline.json", "stormdeck.case_timeline.v0")
    write_json(tmp_path / "temporal_tracks.json", "stormdeck.temporal_tracks.v0")
    write_json(tmp_path / "field_preview.json", "stormdeck.field_preview.v0")

    manifest = mod.build_case_manifest(export_dir=tmp_path, case_id="case-b")

    assert manifest["readiness"]["status"] == "blocked"
    assert "change_summary" in manifest["readiness"]["missing_required"]
    assert "map_overlays" in manifest["readiness"]["missing_optional"]
    assert manifest["artifacts"]["map_overlays"]["required"] is False


def test_cli_writes_stormdeck_case_manifest_json(tmp_path):
    mod = load_module()
    write_json(tmp_path / "case_timeline.json", "stormdeck.case_timeline.v0")
    write_json(tmp_path / "temporal_tracks.json", "stormdeck.temporal_tracks.v0")
    write_json(tmp_path / "change_summary.json", "stormdeck.change_summary.v0")
    write_json(tmp_path / "field_preview_playlist.json", "stormdeck.field_preview_playlist.v0")
    out = tmp_path / "stormdeck_case_manifest.json"

    assert mod.main(["--export-dir", str(tmp_path), "--case-id", "case-c", "--out", str(out)]) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))

    assert payload["schema"] == "stormdeck.case_manifest.v0"
    assert payload["case_id"] == "case-c"
    assert payload["artifacts"]["change_summary"]["filename"] == "change_summary.json"
