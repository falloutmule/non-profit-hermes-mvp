from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "prepare_ci_test_environment.py"


def load_module():
    spec = importlib.util.spec_from_file_location("prepare_ci_test_environment", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def write_fixture_tree(root: Path) -> None:
    event = root / "plugins" / "non-profit-hermes-event" / "__init__.py"
    helpers = root / "google-workspace" / "scripts"
    event.parent.mkdir(parents=True, exist_ok=True)
    helpers.mkdir(parents=True, exist_ok=True)
    event.write_text('source_link="telegram:test-user-12345"\n', encoding="utf-8")
    (helpers / "google_api.py").write_text("SCOPES = ()\n", encoding="utf-8")
    (helpers / "_hermes_home.py").write_text(
        "def get_hermes_home(): return None\n", encoding="utf-8"
    )
    (root / "unrelated.txt").write_text("must not copy\n", encoding="utf-8")


def test_prepare_copies_only_required_fixtures_with_hashes_under_destination(tmp_path: Path) -> None:
    module = load_module()
    fixture_root = tmp_path / "fixtures"
    destination = tmp_path / "isolated-runtime"
    write_fixture_tree(fixture_root)

    evidence = module.prepare(destination, fixture_root=fixture_root)

    assert set(evidence) == {
        "event_source_link",
        "external_cwd",
        "fixtures",
        "google_workspace_scripts",
        "hermes_home",
        "home",
    }
    assert evidence["event_source_link"] == "telegram:test-user-12345"
    assert Path(evidence["external_cwd"]).is_dir()
    assert Path(evidence["google_workspace_scripts"]).is_dir()
    assert Path(evidence["hermes_home"]).is_dir()
    assert Path(evidence["home"]).is_dir()
    assert all(Path(item["destination"]).is_file() for item in evidence["fixtures"].values())
    assert all(item["source_sha256"] == item["destination_sha256"] for item in evidence["fixtures"].values())
    assert all(item["private_findings"] == {} for item in evidence["fixtures"].values())
    assert all(Path(item["destination"]).is_relative_to(destination) for item in evidence["fixtures"].values())
    assert not (destination / "unrelated.txt").exists()
    assert not (destination / "hermes-home" / "unrelated.txt").exists()


def test_prepare_rejects_missing_fixture_nonempty_collision_and_destination_escape(tmp_path: Path) -> None:
    module = load_module()
    fixture_root = tmp_path / "fixtures"
    write_fixture_tree(fixture_root)

    missing = fixture_root / "google-workspace" / "scripts" / "google_api.py"
    missing.unlink()
    with pytest.raises(module.PreparationError, match="FIXTURE_SOURCE_MISSING"):
        module.prepare(tmp_path / "missing", fixture_root=fixture_root)

    write_fixture_tree(fixture_root)
    occupied = tmp_path / "occupied"
    occupied.mkdir()
    (occupied / "existing.txt").write_text("collision\n", encoding="utf-8")
    with pytest.raises(module.PreparationError, match="DESTINATION_NOT_EMPTY"):
        module.prepare(occupied, fixture_root=fixture_root)

    with pytest.raises(module.PreparationError, match="DESTINATION_ESCAPE"):
        module.destination_under(tmp_path / "root", Path("..") / "escape")


def test_metadata_and_workflow_truthfully_encode_supported_runtime_versions() -> None:
    module = load_module()

    assert module.runtime_python_supported("3.11")
    assert module.runtime_python_supported("3.12")
    assert module.runtime_python_supported("3.13")
    assert not module.runtime_python_supported("3.14")

    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert 'python-version: ["3.11", "3.12", "3.13"]' in workflow
    assert "python-3.14-unsupported-contract" in workflow
    assert "astral-sh/setup-uv@v5" in workflow
    assert "prepare_ci_test_environment.py" in workflow
    assert "python -m pytest -q --junitxml=" in workflow
    assert "--maxfail" not in workflow
    assert "contents: read" in workflow
    assert "${{ secrets." not in workflow
    assert "hermes gateway" not in workflow.lower()

    metadata = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'requires-python = ">=3.11,<3.14"' in metadata

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "Non-Profit Hermes v1.0.0 supports Python 3.11–3.13." in readme
    assert "Python 3.14 is not supported because Hermes Agent 0.18.2 requires Python <3.14." in readme
