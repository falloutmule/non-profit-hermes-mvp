"""Deterministic and synthetic-local tests for semantic ACL repair."""
from __future__ import annotations

import importlib.util
import os
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "google_oauth_acl.py"


def load_module():
    spec = importlib.util.spec_from_file_location("google_oauth_acl", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(spec.name, None)
    return module


def test_parser_normalizes_path_headers_and_indentation() -> None:
    acl = load_module()
    first = r"""C:\one\operational.txt
C:\one\operational.txt BUILTIN\Administrators:(I)(F)
                         NT AUTHORITY\SYSTEM:(I)(F)
                         BUILTIN\Users:(RX)
"""
    second = r"""D:\other\candidate.txt
D:\other\candidate.txt    NT AUTHORITY\SYSTEM:(I)(F)
    BUILTIN\Users:(RX)
    BUILTIN\Administrators:(I)(F)
"""
    assert acl.parse_icacls_output(first) == acl.parse_icacls_output(second)


def test_parser_reorders_aces_but_preserves_deny_and_inheritance() -> None:
    acl = load_module()
    one = "C:\\x\\a.txt\n  CONTOSO\\Readers:(I)(RX)\n  CONTOSO\\Blocked:(DENY)(W)\n"
    two = "C:\\y\\b.txt\nCONTOSO\\Blocked:(W)(DENY)\n CONTOSO\\Readers:(RX)(I)\n"
    assert acl.parse_icacls_output(one) == acl.parse_icacls_output(two)
    assert acl.parse_icacls_output(one)[0].effect == "DENY"
    assert acl.parse_icacls_output(one)[1].inheritance == "INHERITED"


def test_true_rights_mismatch_is_rejected() -> None:
    acl = load_module()
    reference = "C:\\x\\a.txt\n  CONTOSO\\Readers:(RX)"
    candidate = "D:\\y\\b.txt\n  CONTOSO\\Readers:(R)"
    assert not acl.acl_equivalent(reference, candidate, snapshotter=lambda path: acl.parse_icacls_output(path))


def test_candidate_preparation_fails_closed_on_acl_mismatch(tmp_path: Path) -> None:
    acl = load_module()
    reference = tmp_path / "reference.bin"
    candidate = tmp_path / "candidate.bin"
    reference.write_bytes(b"reference-fixture")

    def snapshotter(path):
        return (acl.AclAce("CONTOSO\\User", ("F",)),) if Path(path).name.startswith("reference") else ()

    with pytest.raises(acl.AclRepairError) as error:
        acl.prepare_candidate(reference, candidate, b"synthetic-candidate", runner=lambda *args: "", snapshotter=snapshotter)
    assert error.value.code == "ACL_MISMATCH"
    assert not candidate.exists()
    assert reference.read_bytes() == b"reference-fixture"


def test_candidate_preparation_succeeds_with_equivalent_acl(tmp_path: Path) -> None:
    acl = load_module()
    reference = tmp_path / "reference.bin"
    candidate = tmp_path / "candidate.bin"
    reference.write_bytes(b"reference-fixture")
    expected = (acl.AclAce("CONTOSO\\User", ("F",)),)
    result = acl.prepare_candidate(reference, candidate, b"synthetic-candidate", runner=lambda *args: "", snapshotter=lambda path: expected)
    assert result == candidate
    assert candidate.read_bytes() == b"synthetic-candidate"
    assert reference.read_bytes() == b"reference-fixture"


def test_real_synthetic_local_file_acl_capture_and_preparation(tmp_path: Path) -> None:
    if sys.platform != "win32" or shutil.which("icacls") is None:
        pytest.skip("Windows icacls is required for the local ACL proof")
    acl = load_module()
    reference = tmp_path / "reference.bin"
    candidate = tmp_path / "candidate.bin"
    reference.write_bytes(b"reference-fixture")
    acl.prepare_candidate(reference, candidate, b"synthetic-candidate")
    assert acl.acl_equivalent(reference, candidate)
    assert reference.read_bytes() == b"reference-fixture"


def test_atomic_promotion_success(tmp_path: Path) -> None:
    acl = load_module()
    operational = tmp_path / "operational.bin"
    candidate = tmp_path / "candidate.bin"
    backup = tmp_path / "backup.bin"
    operational.write_bytes(b"old-operational")
    candidate.write_bytes(b"new-candidate")
    snapshotter = lambda path: (acl.AclAce("CONTOSO\\User", ("F",)),)
    acl.atomic_promote(operational, candidate, snapshotter=snapshotter, backup_path=backup)
    assert operational.read_bytes() == b"new-candidate"
    assert not candidate.exists()
    assert not backup.exists()


def test_atomic_promotion_rolls_back_on_injected_replacement_failure(tmp_path: Path) -> None:
    acl = load_module()
    operational = tmp_path / "operational.bin"
    candidate = tmp_path / "candidate.bin"
    backup = tmp_path / "backup.bin"
    operational.write_bytes(b"old-operational")
    candidate.write_bytes(b"new-candidate")
    snapshotter = lambda path: (acl.AclAce("CONTOSO\\User", ("F",)),)

    def fail_candidate_replace(source, destination):
        if Path(source) == candidate:
            raise OSError("injected")
        os.replace(source, destination)

    with pytest.raises(acl.AclRepairError) as error:
        acl.atomic_promote(operational, candidate, snapshotter=snapshotter, replace=fail_candidate_replace, backup_path=backup)
    assert error.value.code == "PROMOTION_FAILED"
    assert candidate.read_bytes() == b"new-candidate"
    assert not backup.exists()


def test_atomic_promotion_rolls_back_on_promoted_acl_verification_failure(tmp_path: Path) -> None:
    acl = load_module()
    operational = tmp_path / "operational.bin"
    candidate = tmp_path / "candidate.bin"
    backup = tmp_path / "backup.bin"
    operational.write_bytes(b"old-operational")
    candidate.write_bytes(b"new-candidate")
    good = (acl.AclAce("CONTOSO\\User", ("F",)),)
    bad = (acl.AclAce("CONTOSO\\User", ("R",)),)
    calls = 0

    def snapshotter(path):
        nonlocal calls
        calls += 1
        return good if calls < 3 else bad

    with pytest.raises(acl.AclRepairError) as error:
        acl.atomic_promote(operational, candidate, snapshotter=snapshotter, backup_path=backup)
    assert error.value.code == "PROMOTED_ACL_MISMATCH"
    assert operational.read_bytes() == b"old-operational"
    assert candidate.read_bytes() == b"new-candidate"
    assert not backup.exists()
