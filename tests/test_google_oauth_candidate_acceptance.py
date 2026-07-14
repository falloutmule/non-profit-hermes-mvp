"""Offline fake-only tests for redacted OAuth candidate-acceptance diagnostics."""
from __future__ import annotations

import importlib.util
import inspect
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "google_oauth_candidate_acceptance.py"


def load_module():
    spec = importlib.util.spec_from_file_location("candidate_acceptance", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(spec.name, None)
    return module


def metadata(evaluator, **overrides):
    values = {
        "credential_valid": True,
        "credential_expired": False,
        "granted_scope_names": frozenset({"calendar.readonly", "spreadsheets.readonly"}),
        "expected_scope_names": frozenset({"calendar.readonly", "spreadsheets.readonly"}),
        "client_identity_matches": True,
        "refresh_token_present": True,
        "serialized_json_valid": True,
        "serialized_shape_expected": True,
        "serialized_field_names": frozenset({"token", "refresh_token", "scopes"}),
        "token_type_expected": True,
        "candidate_acl_matches": True,
        "existing_token_unchanged": True,
    }
    values.update(overrides)
    return evaluator.CandidateAcceptanceMetadata(**values)


def assert_code(evaluator, expected_code: str, **overrides) -> None:
    result = evaluator.evaluate_candidate_acceptance(metadata(evaluator, **overrides))
    assert result["accepted"] is False
    assert result["invariant_code"] == expected_code


def test_credential_not_valid_is_reported_without_values() -> None:
    evaluator = load_module()
    candidate = metadata(evaluator, credential_valid=False)

    assert evaluator.evaluate_candidate_acceptance(candidate) == {
        "accepted": False,
        "invariant_code": "CREDENTIAL_NOT_VALID",
        "checks": {
            "credential_valid": False,
            "credential_not_expired": True,
            "granted_scope_set_exact": True,
            "client_identity_matches": True,
            "refresh_token_present": True,
            "serialized_json_valid": True,
            "serialized_shape_expected": True,
            "serialized_field_names_allowed": True,
            "token_type_expected": True,
            "candidate_acl_matches": True,
            "existing_token_unchanged": True,
        },
    }


def test_credential_expired_is_reported() -> None:
    assert_code(load_module(), "CREDENTIAL_EXPIRED", credential_expired=True)


def test_broader_granted_scope_set_is_rejected() -> None:
    assert_code(
        load_module(),
        "GRANTED_SCOPE_SET_MISMATCH",
        granted_scope_names=frozenset({"calendar.readonly", "spreadsheets.readonly", "drive.readonly"}),
    )


def test_narrower_granted_scope_set_is_rejected() -> None:
    assert_code(
        load_module(),
        "GRANTED_SCOPE_SET_MISMATCH",
        granted_scope_names=frozenset({"calendar.readonly"}),
    )


def test_client_identity_mismatch_is_reported() -> None:
    assert_code(load_module(), "CLIENT_IDENTITY_MISMATCH", client_identity_matches=False)


def test_refresh_token_missing_is_reported_by_presence_only() -> None:
    assert_code(load_module(), "REFRESH_TOKEN_MISSING", refresh_token_present=False)


def test_serialized_json_invalid_is_reported() -> None:
    assert_code(load_module(), "SERIALIZED_JSON_INVALID", serialized_json_valid=False)


def test_serialized_shape_unexpected_is_reported_from_field_names_only() -> None:
    assert_code(
        load_module(),
        "SERIALIZED_SHAPE_UNEXPECTED",
        serialized_field_names=frozenset({"token", "unrecognized_field"}),
    )


def test_token_type_unexpected_is_reported() -> None:
    assert_code(load_module(), "TOKEN_TYPE_UNEXPECTED", token_type_expected=False)


def test_candidate_acl_mismatch_is_reported() -> None:
    assert_code(load_module(), "CANDIDATE_ACL_MISMATCH", candidate_acl_matches=False)


def test_existing_token_changed_is_reported() -> None:
    assert_code(load_module(), "EXISTING_TOKEN_CHANGED", existing_token_unchanged=False)


def test_exact_two_scope_success_and_order_independence() -> None:
    evaluator = load_module()
    result = evaluator.evaluate_candidate_acceptance(
        metadata(
            evaluator,
            granted_scope_names=frozenset({"spreadsheets.readonly", "calendar.readonly"}),
        )
    )
    assert result["accepted"] is True
    assert result["invariant_code"] == "ACCEPTED"


def test_multiple_failure_priority_is_deterministic() -> None:
    evaluator = load_module()
    result = evaluator.evaluate_candidate_acceptance(
        metadata(
            evaluator,
            credential_valid=False,
            credential_expired=True,
            client_identity_matches=False,
        )
    )
    assert result["invariant_code"] == "CREDENTIAL_NOT_VALID"


def test_result_is_json_safe_and_contains_only_redacted_types() -> None:
    evaluator = load_module()
    result = evaluator.evaluate_candidate_acceptance(metadata(evaluator))
    assert set(result) == {"accepted", "invariant_code", "checks"}
    assert type(result["accepted"]) is bool
    assert result["invariant_code"] == "ACCEPTED"
    assert type(result["checks"]) is dict
    assert all(type(name) is str and type(value) is bool for name, value in result["checks"].items())
    assert json.loads(json.dumps(result)) == result


def test_secret_shaped_inputs_are_rejected_and_never_render_values(capsys) -> None:
    evaluator = load_module()
    sentinel = "DO-NOT-RENDER-SECRET-SENTINEL"
    with pytest.raises(TypeError) as constructor_error:
        evaluator.CandidateAcceptanceMetadata(access_token=sentinel)
    assert sentinel not in str(constructor_error.value)
    with pytest.raises(evaluator.CandidateAcceptanceMetadataError) as evaluator_error:
        evaluator.evaluate_candidate_acceptance(sentinel)
    assert sentinel not in str(evaluator_error.value)
    captured = capsys.readouterr()
    assert sentinel not in captured.out
    assert sentinel not in captured.err


def test_evaluator_has_no_network_or_file_io_import_or_path() -> None:
    evaluator = load_module()
    source = inspect.getsource(evaluator)
    forbidden = ("import os", "import pathlib", "import requests", "import urllib", "import google", "open(")
    assert not any(fragment in source for fragment in forbidden)
