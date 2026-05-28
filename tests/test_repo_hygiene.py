from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_github_actions_ci_runs_pytest():
    workflow = ROOT / ".github" / "workflows" / "pytest.yml"
    text = workflow.read_text(encoding="utf-8")

    assert "pytest" in text
    assert "python-version" in text
    assert "pip install" not in text  # keep CI dependency-light unless explicitly approved
    assert "python -m pytest" in text


def test_docs_renders_can_be_tracked_despite_generated_renders_ignore():
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    assert "renders/" in gitignore
    assert "!docs/renders/" in gitignore
    assert "!docs/renders/.gitkeep" in gitignore
    assert (ROOT / "docs" / "renders" / ".gitkeep").exists()
