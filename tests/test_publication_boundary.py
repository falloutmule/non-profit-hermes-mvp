from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path


def _load_checker(source_root: Path):
    script = source_root / "scripts" / "check_publication_boundary.py"
    spec = importlib.util.spec_from_file_location("publication_boundary", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


def test_scan_git_commit_reports_only_path_and_code_for_machine_local_report(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.name", "test")
    _git(repo, "config", "user.email", "test@example.invalid")
    report = repo / "reports" / "status.json"
    report.parent.mkdir()
    report.write_text(
        '{"launcher":"C:\\\\Users\\\\private-user\\\\AppData\\\\Local\\\\hermes\\\\profiles\\\\nonprofit"}\n',
        encoding="utf-8",
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "fixture")

    checker = _load_checker(Path(__file__).resolve().parents[1])
    findings = checker.scan_git_commit(repo, "HEAD")

    assert findings == [
        {"code": "WINDOWS_USER_HOME_PATH", "path": "reports/status.json"}
    ]


def test_scan_git_commit_does_not_treat_a_regular_expression_as_a_user_home(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.name", "test")
    _git(repo, "config", "user.email", "test@example.invalid")
    source = repo / "scripts" / "pattern.py"
    source.parent.mkdir()
    source.write_text('PATTERN = r"/home/([^/\\\\s<>]+)"\n', encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "fixture")

    checker = _load_checker(Path(__file__).resolve().parents[1])

    assert checker.scan_git_commit(repo, "HEAD") == []
