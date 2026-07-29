# Portable Package Report

## Scope

This report closes the NPH-V1-020 portable-package integration slice only. It covers the Python package foundation, canonical schema, OAuth refresh, operations, approved-safe sync, Telegram router, one sanitized package resource, legacy compatibility wrappers, and built-distribution evidence. Unified plugin, profile distribution, runtime doctor, clean-install migration, and production activation are outside this slice.

## Implementation

- Package version remains exactly `1.0.0`.
- `non_profit_hermes/resources/defaults.toml` contains exactly three shareable keys: `version`, `public_marker`, and the seven command names (`daily`, `need`, `donation`, `report`, `task`, `inventory`, `event`).
- `non_profit_hermes.config.load_packaged_defaults()` uses `importlib.resources` plus `tomllib`, returns parsed TOML, and performs no configuration resolution, credential access, directory creation, network access, or writes.
- `pyproject.toml` includes exactly `resources/defaults.toml` as package data. Private-data exclusions and package discovery exclusions remain in place.
- `scripts/non_profit_hermes_schema.py` is now a thin compatibility wrapper over `non_profit_hermes.models`. Its public constants and functions preserve object identity, and its public export order is explicit.
- The four migrated operational scripts remain compatibility wrappers over canonical package modules.

## TDD evidence

### RED

Command:

```text
python -m pytest -q tests/test_portable_package_integration.py tests/test_package_foundation.py tests/test_schema_parity.py
```

Observed before production changes:

```text
7 failed, 16 passed in 3.05s
```

The expected failures proved the missing package resource, missing resource loader, absent package-data declaration, non-wrapper legacy schema, and missing installed-wheel resource behavior.

### GREEN

The same focused command after minimal implementation returned:

```text
23 passed in 3.25s
```

## Commit chain

```text
612452cbdead41b6b5f2ce92410d3f6d277b5bb0 feat: add portable package foundation
d9aacd06401f2ff56bc0b6729d2cd3978e0dda3c refactor: package atomic OAuth refresh
58a7fea909101055c2a934f39b07bc6b8a608a5c refactor: package nonprofit operations
5e37d37442cb445034cb7d5bd26568701f995f03 refactor: package approved-safe sync
b2633a131c77612427cc87764563c3db83afb061 refactor: package Telegram intake router
<this report's containing commit> feat: complete portable package integration
```

The integration commit parent is exactly `b2633a131c77612427cc87764563c3db83afb061`.

## Local verification

### Focused lane

```text
python -m pytest -q tests/test_portable_package_integration.py tests/test_package_foundation.py tests/test_schema_parity.py
23 passed in 3.25s
```

### Full lane

```text
python -m pytest -q
280 passed, 64 subtests passed in 10.45s
```

### Compilation

```text
python -m py_compile non_profit_hermes/*.py scripts/*.py tests/*.py
exit 0; no output
```

### Repository-source import and resource load

```text
python -c "import non_profit_hermes; from non_profit_hermes.config import load_packaged_defaults; print(non_profit_hermes.__version__); print(load_packaged_defaults())"
1.0.0
{'version': '1.0.0', 'public_marker': 'CLEAN_DOCS_DEPLOY_NON_PROFIT_HERMES_002', 'commands': ['daily', 'need', 'donation', 'report', 'task', 'inventory', 'event']}
```

## Distribution build and member inspection

Build command, with `$EVIDENCE_DIR` set to a unique external evidence directory:

```text
uv build --out-dir "$EVIDENCE_DIR/dist"
```

Result:

```text
Successfully built non_profit_hermes-1.0.0.tar.gz
Successfully built non_profit_hermes-1.0.0-py3-none-any.whl
```

Artifact digests:

```text
wheel sha256: 0ab10ab07701363de5494167b6a86d1e8bf509f9f9b4797c5f66dda68af05e06
sdist sha256: f8c9849dad437eacb8724fda28af8a05863114a0cfe27bc83127790860fae948
```

The wheel has exactly 12 members:

```text
non_profit_hermes/__init__.py
non_profit_hermes/approved_safe_sync.py
non_profit_hermes/config.py
non_profit_hermes/models.py
non_profit_hermes/oauth_refresh.py
non_profit_hermes/operations.py
non_profit_hermes/router.py
non_profit_hermes/resources/defaults.toml
non_profit_hermes-1.0.0.dist-info/METADATA
non_profit_hermes-1.0.0.dist-info/RECORD
non_profit_hermes-1.0.0.dist-info/WHEEL
non_profit_hermes-1.0.0.dist-info/top_level.txt
```

Wheel inspection found zero scripts, tests, docs, reports, runtime plugins, authentication files, environment files, databases, logs, memories, sessions, proof files, or public evidence. All seven package Python files plus `defaults.toml` are byte-identical between source and wheel.

The sdist has 40 file members. Its top-level contents are project metadata, README, package sources/resources, generated package metadata, and tests. It contains no scripts, runtime plugins, docs, reports, authentication files, environment files, databases, logs, memories, sessions, proof files, or public evidence.

## Installed-wheel external verification

Install command:

```text
python -m pip install --no-deps --target "$EVIDENCE_DIR/installed" "$EVIDENCE_DIR/dist/non_profit_hermes-1.0.0-py3-none-any.whl"
```

Result:

```text
Successfully installed non-profit-hermes-1.0.0
```

From an external working directory with only the installed target on `PYTHONPATH`, an audit-hook subprocess imported:

```text
non_profit_hermes
non_profit_hermes.config
non_profit_hermes.models
non_profit_hermes.oauth_refresh
non_profit_hermes.operations
non_profit_hermes.approved_safe_sync
non_profit_hermes.router
```

It loaded packaged defaults and returned:

```text
installed-wheel-offline-import-ok
```

The audit hook rejected any attempted network access, credential read, or filesystem write. None occurred. The configured nonexistent credential sentinel remained absent.

## Compatibility verification

From the same external working directory and installed-wheel target:

```text
CLI_HELP non_profit_hermes_ops.py EXIT=0 USAGE=True
CLI_HELP sync_approved_safe_data.py EXIT=0 USAGE=True
CLI_HELP telegram_intake_router.py EXIT=0 USAGE=True
DIRECT_FILE google_oauth_refresh.py EXIT=0
DIRECT_FILE non_profit_hermes_schema.py EXIT=0
EXTERNAL_CLI_CREATED=[]
EXTERNAL_CLI_CHANGED=[]
CREDENTIAL_EXISTS=False
```

Direct file imports of all four operational wrappers preserved their canonical module `__all__` exports by object identity. The schema wrapper preserved every declared public constant/function by object identity. No wrapper mutated the interpreter search path.

## Portability and secret scans

The final scan covered seven canonical package modules, four migrated operational wrappers, the schema wrapper, `defaults.toml`, and this report (14 files). It checked for hardcoded user paths, interpreter search-path mutation, Telegram bot-token shapes, Google API-key shapes, OAuth access-token shapes, raw Telegram chat-ID shapes, and assigned secret literals.

```text
FINAL_SCAN_FILES=14
FINAL_SCAN_FINDINGS=[]
```

`git diff --check` passed, and the exact changed-file set matched the eight-path task allowlist with no outside or missing paths. Final clean-tree verification is rerun after the scoped commit.

## Limitations

- The sdist intentionally contains tests as source-distribution material; the installed wheel does not.
- Physical-device and browser evidence do not apply because this slice has no visible UI change.
- Unified plugin, profile distribution, runtime doctor, disposable profile installation, production migration, and release tagging remain separate downstream tasks.

## No-live-action statement

No live Telegram, Google Sheets, Google Calendar, public-site generation/publication, gateway, plugin, profile, credential, or production-runtime action was performed. Verification used source files, synthetic temporary paths, an external built wheel target, audit hooks, and CLI help/import paths only.
