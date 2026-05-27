import importlib.util
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "stormdeck_serve_bundle_viewer.py"


def load_module():
    spec = importlib.util.spec_from_file_location("stormdeck_serve_bundle_viewer", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_serve_bundle_viewer_cli_help_mentions_launcher_contract():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    for text in ["--host", "--port", "--open", "bundle_dir", "ppi_bundle_viewer.html"]:
        assert text in result.stdout


def test_resolve_server_roots_supports_bundle_dir_and_project_viewer(tmp_path):
    module = load_module()
    project = tmp_path / "project"
    bundle = project / "bundle"
    bundle.mkdir(parents=True)
    viewer_dir = project / "viewer"
    viewer_dir.mkdir(parents=True)
    viewer = viewer_dir / "ppi_bundle_viewer.html"
    viewer.write_text("viewer", encoding="utf-8")

    resolved = module.resolve_server_roots(bundle, project_root=project)

    assert resolved.bundle_dir == bundle.resolve()
    assert resolved.project_root == project.resolve()
    assert resolved.viewer_path == viewer.resolve()
    assert resolved.serve_dir == project.resolve()
    assert resolved.bundle_url_path == "/bundle/"
    assert resolved.viewer_url_path == "/viewer/ppi_bundle_viewer.html"


def test_build_viewer_url_includes_bundle_root_query():
    module = load_module()

    url = module.build_viewer_url(
        host="127.0.0.1",
        port=8765,
        viewer_url_path="/viewer/ppi_bundle_viewer.html",
        bundle_url_path="/bundle/",
    )

    assert url == "http://127.0.0.1:8765/viewer/ppi_bundle_viewer.html?bundleRoot=/bundle/"
