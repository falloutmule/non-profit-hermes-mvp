# COMPLETION_REFRESH_001 — Atomic OAuth Refresh Closeout

## Goal

Close the preserved atomic-refresh branch with offline, disposable synthetic-file evidence only. No Google OAuth credential, token, network call, Telegram action, gateway action, publication, remote Git action, or merge was performed.

## Starting state

- Required branch: `completion-refresh-001`
- Starting HEAD: `36b8298bee46d916bfb01543fb26ef102bb649aa`
- Starting commit subject: `fix: persist Google token refresh atomically`
- Preflight result: `git status --short --branch` returned only `## completion-refresh-001`; worktree was clean.
- Preserved commit `36b8298bee46d916bfb01543fb26ef102bb649aa` was not amended.

## System model

- Durable state owner: the operational token file.
- Ephemeral state owners: the refresh lock, serialized candidate, and exact-byte backup.
- Runtime state owner: the caller-owned in-memory credential; `refresh_credential_in_memory` does not write disk state.
- Inputs: an already-loaded credential, request, operational token path, expected scopes, and injected filesystem seams.
- Output: only a validated candidate may atomically replace the operational token.
- Timing: refresh in memory -> serialize candidate -> validate semantic/ACL/hash invariants -> acquire lock -> write exact backup -> replace -> flush/verify -> remove backup and temporary state.
- Derived, non-secret evidence: SHA-256 hashes, boolean checks, invariant codes, and rollback codes.
- Randomness: none in refresh semantics. Backup names use `mkstemp` only for collision-resistant filesystem allocation; they are not persisted, serialized, or used as semantic input.

## Invariants

- The original operational bytes and ACL must remain unchanged before promotion and after every handled failure.
- A candidate is validated before durable replacement.
- A failed lock write or lock flush must not strand a lock that converts later attempts into false concurrent-refresh failures.
- The integrated public refresh boundary must remove its temporary candidate on success or failure.
- Failed post-replacement paths roll back exact pre-promotion bytes and ACL where rollback succeeds.
- Errors and `refresh_evidence` contain stable codes/hashes only, never credential values.
- Rendering, DOM, audio, and visual randomness do not participate in this persistence system.

## Observed failures and root causes

1. Lock setup failure after `os.open` succeeded left `.refresh.lock` on disk because `__enter__` raised before the context manager could invoke `__exit__`.
2. `refresh_and_persist_credential` left a serialized candidate behind when promotion failed before replacement. The lower-level promotion seam intentionally preserves its candidate for its direct caller; the production integration seam had no `finally` cleanup.

## Changes

- `scripts/google_oauth_refresh.py`
  - Close and remove an acquired lock when lock initialization fails during `os.write` or `os.fsync`.
  - Wrap validation/promotion in `try/finally` so the integrated refresh boundary removes its temporary candidate on all outcomes after preparation.
- `tests/test_google_oauth_refresh.py`
  - Added a Windows `tmp_path` test proving a synthetic lock-write failure returns `LOCK_FAILED`, preserves the original operational bytes, leaves the candidate untouched for the direct promotion seam, and removes the lock.
  - Added an integrated synthetic replacement-failure test proving original bytes, candidate, backup, and lock cleanup behavior.

## Disposable Windows evidence paths

The red tests ran exclusively in pytest-managed disposable Windows temporary directories:

- `C:\Users\fallo\AppData\Local\Temp\pytest-of-fallo\pytest-372\test_lock_write_failure_remove0`
- `C:\Users\fallo\AppData\Local\Temp\pytest-of-fallo\pytest-374\test_integrated_replace_failur0`

Those directories contained only synthetic JSON and pytest artifacts. No production token path was opened.

## Commands and results

Pre-change baseline:

- `git status --short --branch && git rev-parse HEAD && git branch --show-current && git log --oneline -3`
  - Exit 0; branch `completion-refresh-001`; exact required HEAD; clean status.
- `python -m pytest tests/test_google_oauth_refresh.py -q`
  - Exit 0; `19 passed in 0.71s`.
- `python -m pytest -q`
  - Exit 0; `228 passed, 64 subtests passed in 4.18s`.
- `python -m py_compile scripts/*.py tests/*.py && git diff --check`
  - Exit 0; no output.

TDD evidence for the two concrete defects:

- `python -m pytest tests/test_google_oauth_refresh.py::test_lock_write_failure_removes_stale_lock_and_preserves_operational_token -q`
  - Before fix: exit 1; failed at `assert not lock.exists()`.
  - After fix: exit 0; `1 passed in 0.03s`.
- `python -m pytest tests/test_google_oauth_refresh.py::test_integrated_replace_failure_cleans_temporary_candidate_and_lock -q`
  - Before fix: exit 1; failed at `assert not candidate.exists()`.
  - After fix: included in the focused suite below.

Post-change verification:

- `python -m pytest tests/test_google_oauth_refresh.py -q`
  - Exit 0; `21 passed in 0.28s`.
- `python -m pytest -q`
  - Exit 0; `230 passed, 64 subtests passed in 4.02s`.
- `python -m py_compile scripts/*.py tests/*.py && git diff --check`
  - Exit 0; no checker failures. Git emitted only expected working-tree LF-to-CRLF notices.

## Failure-path coverage exercised with synthetic files

- Refresh endpoint failure preserves the operational token.
- Missing refresh token, invalid credential, scope mismatch, and client-identity mismatch reject before promotion.
- Serialization and candidate preparation/ACL failure preserve operational data and clean the candidate.
- Backup failure and pre-replace replacement failure preserve the operational token.
- Post-replace validation failure rolls back exact original bytes.
- Rollback failure produces a distinct rollback code.
- Existing lock produces `CONCURRENT_REFRESH` without mutation.
- New lock-write failure coverage proves acquired-lock cleanup.
- New integrated replacement-failure coverage proves candidate, backup, and lock cleanup.
- Secret-free evidence excludes synthetic refresh/access token and client values.
- Ops and sync callers use the durable refresh boundary under fakes; no live call is made by those tests.

## Privacy and runtime boundary

All tests use `FakeCredential`, synthetic request objects, injected candidate writers, injected snapshotters, injected flushers, and injected replacers. No test reads `C:\Users\fallo\AppData\Local\hermes\google_token.json`, invokes a Google endpoint, or uses a real OAuth credential. The report intentionally contains no credential values, token values, or production hashes.

## Limitations and risks

- Permission/ACL and flush failures are deterministically injected `OSError` paths; this closeout did not alter Windows ACLs or test against a real production token because the task explicitly forbids that access.
- A direct caller of the lower-level `promote_refresh_candidate_atomically` retains its candidate on a failed promotion by existing API behavior; the production `refresh_and_persist_credential` path now removes it in `finally`.
- Physical user/Google service acceptance is intentionally untested.
- Git emits LF-to-CRLF working-tree notices only; `git diff --check` remains clean.

## Post-commit state

The focused closeout commit SHA and clean post-commit status are recorded in the Kanban completion handoff after this report is committed; this file cannot self-reference its own future Git object ID without amending or creating a second commit.

## Checker focus

Confirm that the two new `finally`-style cleanup boundaries do not alter valid promotion behavior, that direct lower-level candidate-retention semantics remain intentional, and that no report/test fixture contains a real credential or token.
