"""Pure, redacted OAuth candidate-acceptance diagnostics.

This module accepts only derived, nonsecret metadata.  It performs no I/O and does
not construct, read, retain, or render OAuth credential material.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final


_ALLOWED_SERIALIZED_FIELD_NAMES: Final[frozenset[str]] = frozenset(
    {
        "account",
        "client_id",
        "client_secret",
        "expiry",
        "refresh_token",
        "scopes",
        "token",
        "token_uri",
        "type",
        "universe_domain",
    }
)

_CHECK_ORDER: Final[tuple[tuple[str, str], ...]] = (
    ("credential_valid", "CREDENTIAL_NOT_VALID"),
    ("credential_not_expired", "CREDENTIAL_EXPIRED"),
    ("granted_scope_set_exact", "GRANTED_SCOPE_SET_MISMATCH"),
    ("client_identity_matches", "CLIENT_IDENTITY_MISMATCH"),
    ("refresh_token_present", "REFRESH_TOKEN_MISSING"),
    ("serialized_json_valid", "SERIALIZED_JSON_INVALID"),
    ("serialized_shape_expected", "SERIALIZED_SHAPE_UNEXPECTED"),
    ("serialized_field_names_allowed", "SERIALIZED_SHAPE_UNEXPECTED"),
    ("token_type_expected", "TOKEN_TYPE_UNEXPECTED"),
    ("candidate_acl_matches", "CANDIDATE_ACL_MISMATCH"),
    ("existing_token_unchanged", "EXISTING_TOKEN_CHANGED"),
)


class CandidateAcceptanceMetadataError(ValueError):
    """Raised for invalid metadata without including caller-supplied values."""

    def __init__(self) -> None:
        super().__init__("candidate acceptance metadata is invalid")


@dataclass(frozen=True)
class CandidateAcceptanceMetadata:
    """Only derived metadata permitted across the diagnostic boundary."""

    credential_valid: bool
    credential_expired: bool
    granted_scope_names: frozenset[str]
    expected_scope_names: frozenset[str]
    client_identity_matches: bool
    refresh_token_present: bool
    serialized_json_valid: bool
    serialized_shape_expected: bool
    serialized_field_names: frozenset[str]
    token_type_expected: bool
    candidate_acl_matches: bool
    existing_token_unchanged: bool


def _require_nonsecret_metadata(metadata: CandidateAcceptanceMetadata) -> None:
    if type(metadata) is not CandidateAcceptanceMetadata:
        raise CandidateAcceptanceMetadataError()

    boolean_names = (
        "credential_valid",
        "credential_expired",
        "client_identity_matches",
        "refresh_token_present",
        "serialized_json_valid",
        "serialized_shape_expected",
        "token_type_expected",
        "candidate_acl_matches",
        "existing_token_unchanged",
    )
    if any(type(getattr(metadata, name)) is not bool for name in boolean_names):
        raise CandidateAcceptanceMetadataError()

    set_names = ("granted_scope_names", "expected_scope_names", "serialized_field_names")
    for name in set_names:
        value = getattr(metadata, name)
        if type(value) is not frozenset or any(type(item) is not str for item in value):
            raise CandidateAcceptanceMetadataError()


def evaluate_candidate_acceptance(metadata: CandidateAcceptanceMetadata) -> dict[str, object]:
    """Return deterministic invariant diagnostics using no credential values."""
    _require_nonsecret_metadata(metadata)

    checks: dict[str, bool] = {
        "credential_valid": metadata.credential_valid,
        "credential_not_expired": not metadata.credential_expired,
        "granted_scope_set_exact": metadata.granted_scope_names == metadata.expected_scope_names,
        "client_identity_matches": metadata.client_identity_matches,
        "refresh_token_present": metadata.refresh_token_present,
        "serialized_json_valid": metadata.serialized_json_valid,
        "serialized_shape_expected": metadata.serialized_shape_expected,
        "serialized_field_names_allowed": metadata.serialized_field_names.issubset(
            _ALLOWED_SERIALIZED_FIELD_NAMES
        ),
        "token_type_expected": metadata.token_type_expected,
        "candidate_acl_matches": metadata.candidate_acl_matches,
        "existing_token_unchanged": metadata.existing_token_unchanged,
    }
    for check_name, invariant_code in _CHECK_ORDER:
        if not checks[check_name]:
            return {"accepted": False, "invariant_code": invariant_code, "checks": checks}
    return {"accepted": True, "invariant_code": "ACCEPTED", "checks": checks}
