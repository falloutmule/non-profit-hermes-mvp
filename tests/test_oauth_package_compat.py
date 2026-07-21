"""Package-boundary and legacy-wrapper tests for atomic OAuth refresh."""
from __future__ import annotations

import ast
import importlib.util
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_PATH = ROOT / "non_profit_hermes" / "oauth_refresh.py"
LEGACY_PATH = ROOT / "scripts" / "google_oauth_refresh.py"
EXPECTED_PUBLIC_NAMES = (
    "PreparedRefreshCandidate",
    "RefreshPersistenceError",
    "RefreshPromotion",
    "RefreshValidation",
    "prepare_refresh_candidate",
    "promote_refresh_candidate_atomically",
    "refresh_and_persist_credential",
    "refresh_credential_in_memory",
    "refresh_evidence",
    "rollback_refresh_promotion",
    "validate_refresh_candidate",
)


def _load_legacy_wrapper():
    spec = importlib.util.spec_from_file_location("legacy_google_oauth_refresh", LEGACY_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_package_owns_the_complete_public_refresh_contract() -> None:
    from non_profit_hermes import oauth_refresh

    assert oauth_refresh.__all__ == EXPECTED_PUBLIC_NAMES
    assert all(getattr(oauth_refresh, name).__module__ == oauth_refresh.__name__ for name in EXPECTED_PUBLIC_NAMES)


def test_package_source_is_portable_and_self_contained() -> None:
    source = PACKAGE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules = {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    imported_modules.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )

    assert "sys.path" not in source
    assert "C:\\Users\\" not in source
    assert "/Users/" not in source
    assert "TOKEN_PATH" not in source
    assert "GOOGLE_TOKEN" not in source
    assert not any(module == "scripts" or module.startswith("scripts.") for module in imported_modules)
    assert "google_oauth_acl" not in imported_modules
    assert "google_oauth_candidate_acceptance" not in imported_modules


def test_legacy_wrapper_reexports_canonical_objects_by_identity() -> None:
    from non_profit_hermes import oauth_refresh

    legacy = _load_legacy_wrapper()
    assert legacy.__all__ == oauth_refresh.__all__
    assert all(getattr(legacy, name) is getattr(oauth_refresh, name) for name in oauth_refresh.__all__)


def test_legacy_wrapper_contains_only_package_delegation() -> None:
    source = LEGACY_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)

    assert not any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) for node in ast.walk(tree))
    assert len(source.splitlines()) <= 30
    assert "non_profit_hermes.oauth_refresh" in source
    assert "hashlib" not in source
    assert "tempfile" not in source
    assert "os.replace" not in source
    assert "class RefreshPersistenceError" not in source


def test_package_and_legacy_wrapper_import_from_external_cwd(tmp_path: Path) -> None:
    code = f"""
import importlib.util
import pathlib
import sys
from non_profit_hermes import oauth_refresh

scripts_dir = pathlib.Path({os.fspath(ROOT / 'scripts')!r}).resolve()
assert all(pathlib.Path(entry or '.').resolve() != scripts_dir for entry in sys.path)
spec = importlib.util.spec_from_file_location('external_legacy_refresh', {os.fspath(LEGACY_PATH)!r})
assert spec and spec.loader
legacy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(legacy)
assert all(getattr(legacy, name) is getattr(oauth_refresh, name) for name in oauth_refresh.__all__)
"""
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.fspath(ROOT)
    environment["PYTHONNOUSERSITE"] = "1"

    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == ""


def test_legacy_wrapper_file_execution_needs_no_pythonpath(tmp_path: Path) -> None:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = ""
    environment["PYTHONNOUSERSITE"] = "1"

    completed = subprocess.run(
        [sys.executable, os.fspath(LEGACY_PATH)],
        cwd=tmp_path,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == ""
