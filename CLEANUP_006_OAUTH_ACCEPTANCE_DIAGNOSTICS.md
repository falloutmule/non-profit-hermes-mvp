# CLEANUP-006B-R2D — Redacted OAuth Candidate-Acceptance Diagnostics

## Defect repaired

The previous repository-only post-exchange diagnostic surfaced only an exception class. It did not identify the acceptance invariant that failed. This module provides a pure, redacted evaluator so a separately authorized future reconnect can report one stable failure code without emitting OAuth material.

This is not an OAuth implementation. It does not generate authorization URLs, exchange codes, call Google, inspect a credential file, access Sheets or Calendar, persist a token, or mutate runtime state.

## State and boundary model

- State owner: the future authorized reconnect/persistence workflow owns candidate and durable credential state. The evaluator is stateless.
- Inputs: `CandidateAcceptanceMetadata` contains only derived booleans, `frozenset[str]` scope names, a safe identity-equality boolean, and serialized field names. It has no OAuth credential or provider-payload field.
- Output: exactly `{"accepted": bool, "invariant_code": str, "checks": {str: bool}}`.
- Durable state: none. The evaluator writes no cache, evidence, file, or external resource.
- Failure behavior: an invalid metadata object raises `CandidateAcceptanceMetadataError` with a constant value-free message before evaluation. The evaluator makes no mutation, so rollback is not applicable.
- Determinism: no clock, random source, network, file path, environment read, or process state affects a result. Scope comparisons use set equality and are ordering-independent.

## Safe input schema

`CandidateAcceptanceMetadata` accepts only these fields:

- `credential_valid: bool`
- `credential_expired: bool`
- `granted_scope_names: frozenset[str]`
- `expected_scope_names: frozenset[str]`
- `client_identity_matches: bool`
- `refresh_token_present: bool`
- `serialized_json_valid: bool`
- `serialized_shape_expected: bool`
- `serialized_field_names: frozenset[str]`
- `token_type_expected: bool`
- `candidate_acl_matches: bool`
- `existing_token_unchanged: bool`

The input schema deliberately has no field for an access token, refresh-token value, authorization code, client secret, client ID, callback URL, authorization header, provider payload, or credential object. Extra constructor fields fail at the Python API boundary. Invalid evaluator inputs fail using a constant error message and are never rendered by the module.

`serialized_field_names` is names only, never serialized values. The allowed names are: `account`, `client_id`, `client_secret`, `expiry`, `refresh_token`, `scopes`, `token`, `token_uri`, `type`, and `universe_domain`. These are schema labels, not values or evidence.

## Result contract and deterministic priority

`checks` always carries safe booleans for every check. `invariant_code` identifies exactly the first failed invariant in this fixed priority order:

1. `CREDENTIAL_NOT_VALID`
2. `CREDENTIAL_EXPIRED`
3. `GRANTED_SCOPE_SET_MISMATCH`
4. `CLIENT_IDENTITY_MISMATCH`
5. `REFRESH_TOKEN_MISSING`
6. `SERIALIZED_JSON_INVALID`
7. `SERIALIZED_SHAPE_UNEXPECTED` (false structural flag or a field name outside the allowlist)
8. `TOKEN_TYPE_UNEXPECTED`
9. `CANDIDATE_ACL_MISMATCH`
10. `EXISTING_TOKEN_CHANGED`
11. `ACCEPTED` (all checks true; the only code with `accepted: true`)

The granted scope check requires exact set equality: a broader set is rejected, a narrower set is rejected, and the same names in a different order are accepted. The future caller must supply the exact approved expected set; this evaluator does not invent or broaden it.

## Fake-only test evidence

All tests use literal safe metadata and perform no OAuth, Google, network, filesystem, Sheets, Calendar, authorization, exchange, or token operation.

- Initial vertical RED: the first credential-validity test failed because the new evaluator file did not yet exist (`FileNotFoundError`), proving the behavior was absent.
- Initial GREEN: after the evaluator was added and the test loader was made compatible with Python 3.14 dataclasses, the first test passed.
- Focused suite: `C:/Python314/python.exe -m pytest tests/test_google_oauth_candidate_acceptance.py -v` reported `16 passed`.
- Coverage includes every rejection code, exact two-scope success, broader/narrower scope denials, scope-order independence, deterministic multi-failure priority, JSON-safe return shape, secret-shaped input rejection without sentinel rendering, and a source-level no-network/no-file-I/O guard.

## Future authorized reconnect integration guidance

A separately authorized future reconnect may perform its own approved exchange and validation outside this module. Before calling this evaluator, that workflow must reduce candidate state to the safe schema above and must not pass a credential object or any secret value.

The caller should compare scope names as an exact set, derive identity equality without carrying identity values, reduce refresh-token status to presence only, reduce serialization to validity/shape flags and field names, and derive the ACL/existing-token checks before evaluation. It may log only the returned invariant code and boolean checks. Acceptance from this evaluator is diagnostic approval only; it does not authorize persistence. Any future persistence must remain separately authorized, validate before mutating live state, use explicit versioning/migration where applicable, and retain its own transactional rollback behavior.

## Live status

UNTESTED LIVE. No Google API, OAuth endpoint, authorization URL, code exchange, credential/token file, callback, Sheets, Calendar, gateway, plugin, or runtime service was touched. This document does not claim reconnect or live credential repair success.
