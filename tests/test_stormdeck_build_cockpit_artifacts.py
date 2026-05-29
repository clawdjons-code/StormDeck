from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "stormdeck_build_cockpit_artifacts.py"


def read_script():
    return SCRIPT.read_text(encoding="utf-8")


def test_cockpit_artifact_builder_writes_field_preview_playlist_and_map_overlays():
    source = read_script()

    for contract in [
        "field_preview_playlist.json",
        "vertical_slice_playlist.json",
        "map_overlays.json",
        "ppi_tprt_replay_index.json",
        "build_field_preview_from_cfradial",
        "build_field_preview_playlist",
        "build_vertical_slice_from_cfradial",
        "build_vertical_slice_playlist",
        "filter_playlist_previews",
        "build_map_overlays",
        "stormdeck.map_overlay_config.v0",
        "--field",
        "--sweep-index",
        "--vertical-slice-out",
        "--skip-vertical-slice",
        "--map-config",
    ]:
        assert contract in source


def test_cockpit_artifact_builder_keeps_source_files_external_to_bundle():
    source = read_script()

    for contract in [
        "resolve_volume_files",
        "volumes[].file",
        "Source CfRadial file(s) missing",
        "No source CfRadial files found",
    ]:
        assert contract in source
